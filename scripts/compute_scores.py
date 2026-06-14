"""Compute per-district sentiment scores into analytics_districtscore.

Replaces the former Django `run_pipeline --score-only` step. For every district
with posts in the window (default: last 30 days):

    avg_sentiment   mean sentiment_score of processed posts
    post_count      processed posts in the window
    issue_count     negative posts in the window
    overall_score   0-10 composite:
                      50% sentiment (-1..+1 → 0..10)
                    + 30% issue-free ratio
                    + 20% activity bonus (saturates at 50 posts)
    grade           A ≥8, B ≥6, C ≥4, D ≥2, else F
    topic_breakdown per-topic post count + average sentiment

One row per (district, period); re-running the same window updates in place.

Usage (from the project root):
    python -m scripts.compute_scores             # last 30 days
    python -m scripts.compute_scores --days 7    # weekly score
"""

import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import District, DistrictScore, SocialPost, TopicCategory, socialpost_topics


def _grade(score: float) -> str:
    return ("A" if score >= 8 else
            "B" if score >= 6 else
            "C" if score >= 4 else
            "D" if score >= 2 else "F")


def run(days: int = 30) -> int:
    """Score every district with posts in the window; returns rows written."""
    # Snap the window to UTC day boundaries so re-runs on the same day update
    # the same row instead of inserting near-duplicate periods.
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    period_end = today + timedelta(days=1)
    period_start = period_end - timedelta(days=days)

    written = 0
    with SessionLocal() as s:
        # Effective post date = original_date when known, else scraped_at -
        # the same definition the feedbacks view and the RAG filters use.
        eff_date = func.coalesce(SocialPost.original_date, SocialPost.scraped_at)
        in_window = (
            SocialPost.processed_at.isnot(None),
            SocialPost.district_id.isnot(None),
            eff_date >= period_start,
        )

        stats = s.execute(
            select(
                SocialPost.district_id,
                func.count(SocialPost.id),
                func.avg(SocialPost.sentiment_score),
                func.count(SocialPost.id).filter(SocialPost.sentiment_label == "Negative"),
            )
            .where(*in_window)
            .group_by(SocialPost.district_id)
        ).all()

        topic_rows = s.execute(
            select(
                SocialPost.district_id,
                TopicCategory.name,
                func.count(SocialPost.id),
                func.avg(SocialPost.sentiment_score),
            )
            .join(socialpost_topics, socialpost_topics.c.socialpost_id == SocialPost.id)
            .join(TopicCategory, TopicCategory.id == socialpost_topics.c.topiccategory_id)
            .where(*in_window)
            .group_by(SocialPost.district_id, TopicCategory.name)
        ).all()

        breakdowns: dict[int, dict] = {}
        for district_id, topic, count, avg in topic_rows:
            breakdowns.setdefault(district_id, {})[topic] = {
                "count": count,
                "avg_sentiment": round(float(avg or 0.0), 4),
            }

        names = dict(s.execute(select(District.id, District.name)).all())

        for district_id, post_count, avg_sentiment, issue_count in stats:
            avg_sentiment = float(avg_sentiment or 0.0)
            issue_ratio = issue_count / max(post_count, 1)
            overall = (
                0.5 * ((avg_sentiment + 1) / 2) * 10
                + 0.3 * (1 - issue_ratio) * 10
                + 0.2 * min(post_count / 50, 1) * 10
            )
            overall = round(max(0.0, min(10.0, overall)), 2)

            existing = s.scalar(
                select(DistrictScore).where(
                    DistrictScore.district_id == district_id,
                    DistrictScore.period_start == period_start,
                    DistrictScore.period_end == period_end,
                )
            )
            row = existing or DistrictScore(
                district_id=district_id,
                period_start=period_start,
                period_end=period_end,
            )
            row.avg_sentiment = round(avg_sentiment, 4)
            row.post_count = post_count
            row.issue_count = issue_count
            row.overall_score = overall
            row.grade = _grade(overall)
            row.topic_breakdown = breakdowns.get(district_id, {})
            row.computed_at = datetime.now(timezone.utc)
            s.add(row)
            written += 1
            print(f"  {names.get(district_id, district_id)}: {overall}/10 ({row.grade}) - {post_count} posts")

        s.commit()

    print(f"Done! {written} district scores written for the last {days} days.")
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=30, help="Scoring window in days")
    args = ap.parse_args()
    run(days=args.days)


if __name__ == "__main__":
    main()
