"""NLP-process social posts: sentiment + topics + language + district assignment.

Replaces the former Django `run_pipeline --process-only` step. For every
unprocessed post (processed_at IS NULL, or everything with --force):

1. clean text, detect language
2. sentiment via cardiffnlp/twitter-xlm-roberta-base-sentiment (batched)
3. zero-shot topics via MoritzLaurer/mDeBERTa-v3-base-mnli-xnli
4. spaCy NER location extraction → location_name (when empty)
5. district assignment, quarter > sector > city precedence:
   quarter / sector names matched in the content and location hints
   (word-boundary, longest-first, diacritic-normalised)

Work is committed per small chunk so a crash or a Supabase pooler timeout
never loses more than a few rows of work, and the slow model inference always
happens outside any open transaction.

Usage (from the project root):
    python -m scripts.process_posts                 # process new posts
    python -m scripts.process_posts --force         # re-process everything
    python -m scripts.process_posts --limit 20      # smoke test
    python -m scripts.process_posts --device 0      # GPU
"""

import argparse
import re
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import District, SocialPost, TopicCategory

# Romanian/diacritic-aware word-char class (same as app.rag.pipeline).
_WORD = "0-9a-zăâîșț"

# Fold Romanian diacritics (both comma-below and legacy cedilla forms) to
# ASCII so quarter names match pastes typed with or without diacritics
# ("Grozăvești" ↔ "grozavesti").
_DIACRITICS = str.maketrans({
    "ă": "a", "â": "a", "î": "i", "ș": "s", "ş": "s", "ț": "t", "ţ": "t",
    "Ă": "a", "Â": "a", "Î": "i", "Ș": "s", "Ş": "s", "Ț": "t", "Ţ": "t",
})

_SECTOR_RE = re.compile(r"\bsector(?:ul)?\s*([1-6])\b", re.IGNORECASE)


def _norm(text: str) -> str:
    return (text or "").lower().translate(_DIACRITICS)


class DistrictResolver:
    """Resolve a post to a District: quarter > sector > city."""

    def __init__(self, session):
        districts = session.scalars(select(District)).all()
        self.by_id = {d.id: d for d in districts}
        self.sectors = {d.name: d for d in districts if d.kind == "sector"}
        self.city = next((d for d in districts if d.kind == "city"), None)
        # (normalised name, district), longest first so 'Titan Nord' beats 'Titan'.
        self.quarters = sorted(
            ((_norm(d.name), d) for d in districts if d.kind == "quarter"),
            key=lambda x: len(x[0]), reverse=True,
        )

    def resolve(self, *texts: str) -> District | None:
        haystack = _norm(" • ".join(t for t in texts if t))
        if not haystack:
            return self.city
        for low, district in self.quarters:
            if low in haystack and re.search(
                rf"(?<![{_WORD}]){re.escape(low)}(?![{_WORD}])", haystack
            ):
                return district
        m = _SECTOR_RE.search(haystack)
        if m:
            sector = self.sectors.get(f"Sector {m.group(1)}")
            if sector:
                return sector
        return self.city


def run(force: bool = False, limit: int = 0, device: int = -1, batch: int = 16) -> int:
    """Process posts; returns the number of rows updated."""
    from interpreters.mood_analyzer import MoodAnalyzer
    from interpreters.utils.text_processing import clean_text, detect_language

    with SessionLocal() as s:
        stmt = select(SocialPost.id).order_by(SocialPost.id)
        if not force:
            stmt = stmt.where(SocialPost.processed_at.is_(None))
        if limit:
            stmt = stmt.limit(limit)
        post_ids = list(s.scalars(stmt))

    if not post_ids:
        print("No unprocessed posts found. All caught up.")
        return 0

    print(f"Processing {len(post_ids)} posts (force={force}) …")
    print("Loading NLP models (sentiment + zero-shot topics + NER) …")
    analyzer = MoodAnalyzer(device=device)

    with SessionLocal() as s:
        resolver = DistrictResolver(s)

    done = 0
    start = time.time()
    for i in range(0, len(post_ids), batch):
        chunk_ids = post_ids[i:i + batch]
        # A fresh short-lived session per chunk; model inference runs before the
        # writes so the Supabase pooler never sees an idle open transaction.
        with SessionLocal() as s:
            posts = s.scalars(
                select(SocialPost).where(SocialPost.id.in_(chunk_ids)).order_by(SocialPost.id)
            ).all()
            topics_by_name = {t.name: t for t in s.scalars(select(TopicCategory))}
            cleaned = [clean_text(p.content or "") for p in posts]
            results = analyzer.analyze_batch(cleaned, batch_size=batch)

            for post, text, result in zip(posts, cleaned, results):
                post.language = detect_language(text) if text else "unknown"
                post.sentiment_score = result["sentiment"]["score"]
                post.sentiment_label = result["sentiment"]["label"]
                post.topic_scores = result["topic_scores"]
                post.topics = [
                    topics_by_name[name] for name in result["topics"]
                    if name in topics_by_name
                ]

                if not post.location_name and result["locations"]:
                    post.location_name = result["locations"][0]["text"][:255]

                if post.district_id is None or force:
                    district = resolver.resolve(post.content, post.location_name)
                    if district:
                        post.district_id = district.id

                post.processed_at = datetime.now(timezone.utc)
            s.commit()
            done += len(posts)

        rate = done / max(time.time() - start, 1e-9)
        print(f"  {done}/{len(post_ids)} ({rate:.1f}/s)")

    print(f"Done! {done} posts processed in {(time.time()-start)/60:.1f} min.")
    return done


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="Re-process already-processed posts")
    ap.add_argument("--limit", type=int, default=0, help="Stop after N posts (0 = all)")
    ap.add_argument("--device", type=int, default=-1, help="-1 = CPU, 0+ = GPU index")
    ap.add_argument("--batch", type=int, default=16, help="Inference/commit batch size")
    args = ap.parse_args()
    run(force=args.force, limit=args.limit, device=args.device, batch=args.batch)


if __name__ == "__main__":
    main()
