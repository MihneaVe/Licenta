"""
Full data pipeline: scrape → NLP process → geocode → store → score districts.

Usage:
    python manage.py run_pipeline                  # Run everything
    python manage.py run_pipeline --scrape-only    # Only scrape, skip NLP
    python manage.py run_pipeline --process-only   # Only process existing unprocessed posts
    python manage.py run_pipeline --score-only     # Only recompute district scores
    python manage.py run_pipeline --source reddit  # Only scrape Reddit
"""

import logging
from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.analytics.models import (
    SocialPost,
    District,
    DistrictScore,
    TopicCategory,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run the full scrape → process → store → score pipeline"

    def add_arguments(self, parser):
        parser.add_argument("--scrape-only", action="store_true")
        parser.add_argument("--process-only", action="store_true")
        parser.add_argument("--score-only", action="store_true")
        parser.add_argument("--source", type=str, choices=["reddit", "google_maps", "facebook"])
        parser.add_argument("--limit", type=int, default=50, help="Max posts per source")

    def handle(self, *args, **options):
        scrape_only = options["scrape_only"]
        process_only = options["process_only"]
        score_only = options["score_only"]
        source_filter = options["source"]
        limit = options["limit"]

        run_all = not (scrape_only or process_only or score_only)

        if run_all or scrape_only:
            self._ensure_districts()
            self._ensure_topics()
            self._scrape(source_filter, limit)

        if run_all or process_only:
            self._process_posts()

        if run_all or score_only:
            self._compute_district_scores()

        self.stdout.write(self.style.SUCCESS("Pipeline complete."))

    # ------------------------------------------------------------------
    # Step 0: Ensure districts and topic categories exist
    # ------------------------------------------------------------------

    def _ensure_districts(self):
        sectors = [
            "Sector 1", "Sector 2", "Sector 3",
            "Sector 4", "Sector 5", "Sector 6",
        ]
        for name in sectors:
            District.objects.get_or_create(name=name, defaults={"city": "București"})
        self.stdout.write(f"Districts: {District.objects.count()}")

    def _ensure_topics(self):
        for value, label in TopicCategory.CATEGORY_CHOICES:
            TopicCategory.objects.get_or_create(name=value)
        self.stdout.write(f"Topic categories: {TopicCategory.objects.count()}")

    # ------------------------------------------------------------------
    # Step 1: Scrape
    # ------------------------------------------------------------------

    def _scrape(self, source_filter, limit):
        from scrapers.utils.helpers import normalize_post, deduplicate_posts

        all_posts = []

        if source_filter in (None, "reddit"):
            all_posts.extend(self._scrape_reddit(limit))

        if source_filter in (None, "google_maps"):
            all_posts.extend(self._scrape_google_maps(limit))

        if source_filter in (None, "facebook"):
            all_posts.extend(self._scrape_facebook(limit))

        all_posts = deduplicate_posts(all_posts)
        self.stdout.write(f"Scraped {len(all_posts)} total posts")

        # Store in DB
        created = 0
        for post in all_posts:
            normalized = normalize_post(post, post["source"])
            _, was_created = SocialPost.objects.get_or_create(
                source=normalized["source"],
                source_id=normalized["source_id"],
                defaults={
                    "content": normalized["content"],
                    "author": normalized["author"],
                    "score": normalized["score"],
                    "latitude": (normalized["coordinates"] or {}).get("lat"),
                    "longitude": (normalized["coordinates"] or {}).get("lng"),
                    "extra_data": normalized["extra"],
                },
            )
            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(f"Stored {created} new posts"))

    def _scrape_reddit(self, limit):
        from scrapers.reddit_scraper import RedditScraper

        client_id = settings.REDDIT_CLIENT_ID
        client_secret = settings.REDDIT_CLIENT_SECRET
        user_agent = settings.REDDIT_USER_AGENT

        if not client_id or not client_secret:
            self.stdout.write(self.style.WARNING(
                "REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set. Skipping Reddit."
            ))
            return []

        self.stdout.write("Scraping Reddit...")
        scraper = RedditScraper(client_id, client_secret, user_agent)
        scraper.scrape_all_defaults(sort="new", limit=limit)

        # Also search for Bucharest-specific civic keywords
        civic_queries = [
            "București infrastructură",
            "Bucharest sector probleme",
            "București trafic",
            "București parcuri",
        ]
        for q in civic_queries:
            try:
                results = scraper.search(q, subreddit_name="Romania", limit=limit // 4)
                scraper.posts.extend(results)
            except Exception as e:
                logger.warning(f"Reddit search '{q}' failed: {e}")

        self.stdout.write(f"  Reddit: {len(scraper.get_posts())} posts")
        return scraper.get_posts()

    def _scrape_google_maps(self, limit):
        import asyncio
        from scrapers.google_maps_scraper import GoogleMapsScraper

        self.stdout.write("Scraping Google Maps reviews...")
        scraper = GoogleMapsScraper(headless=True)
        try:
            asyncio.run(scraper.scrape_all_defaults(max_reviews_per_place=limit // 4))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  Google Maps scrape failed: {e}"))
            return []

        self.stdout.write(f"  Google Maps: {len(scraper.get_posts())} reviews")
        return scraper.get_posts()

    def _scrape_facebook(self, limit):
        import asyncio
        from scrapers.facebook_groups_scraper import FacebookGroupsScraper

        self.stdout.write("Scraping Facebook groups...")
        scraper = FacebookGroupsScraper(headless=True)
        try:
            asyncio.run(scraper.scrape_all_defaults(
                max_posts_per_group=limit // 2, scroll_count=5
            ))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  Facebook scrape failed: {e}"))
            return []

        self.stdout.write(f"  Facebook: {len(scraper.get_posts())} posts")
        return scraper.get_posts()

    # ------------------------------------------------------------------
    # Step 2: NLP Processing
    # ------------------------------------------------------------------

    def _process_posts(self):
        from interpreters.mood_analyzer import MoodAnalyzer
        from interpreters.llm_summarizer import LLMSummarizer
        from interpreters.utils.text_processing import clean_text, detect_language
        from geo.geocoder import GeocoderService

        unprocessed = SocialPost.objects.filter(processed_at__isnull=True)
        count = unprocessed.count()

        if count == 0:
            self.stdout.write("No unprocessed posts found.")
            return

        self.stdout.write(f"Processing {count} posts...")

        analyzer = MoodAnalyzer(device=-1)
        geocoder = GeocoderService()
        llm = LLMSummarizer()
        llm_available = llm.is_available()

        if not llm_available:
            self.stdout.write(self.style.WARNING(
                "Ollama not available — skipping LLM urgency classification"
            ))

        for i, post in enumerate(unprocessed.iterator()):
            try:
                # Clean and detect language
                cleaned = clean_text(post.content)
                post.language = detect_language(cleaned) if cleaned else "unknown"

                # Run NLP analysis
                result = analyzer.analyze(cleaned)

                # Sentiment
                post.sentiment_score = result["sentiment"]["score"]
                post.sentiment_label = result["sentiment"]["label"]
                post.topic_scores = result["topic_scores"]

                # Assign topics
                topic_names = result["topics"]
                if topic_names:
                    topics = TopicCategory.objects.filter(name__in=topic_names)
                    post.topics.set(topics)

                # Geocode locations if not already set
                if not post.latitude and result["locations"]:
                    loc_text = result["locations"][0]["text"]
                    geo_result = geocoder.geocode_location(loc_text)
                    if geo_result:
                        post.latitude = geo_result["lat"]
                        post.longitude = geo_result["lng"]
                        post.location_name = loc_text

                # Assign district from coordinates
                if post.latitude and post.longitude and not post.district:
                    self._assign_district(post, geocoder)

                # LLM urgency classification for negative posts
                if llm_available and post.sentiment_label == "Negative":
                    urgency = llm.classify_urgency(post.content)
                    if not post.extra_data:
                        post.extra_data = {}
                    post.extra_data["urgency"] = urgency

                post.processed_at = timezone.now()
                post.save()

                if (i + 1) % 25 == 0:
                    self.stdout.write(f"  Processed {i + 1}/{count}")

            except Exception as e:
                logger.error(f"Failed to process post {post.id}: {e}")

        self.stdout.write(self.style.SUCCESS(f"Processed {count} posts"))

    def _assign_district(self, post, geocoder):
        """Try to assign a district from coordinates via reverse geocoding."""
        result = geocoder.reverse_geocode(post.latitude, post.longitude)
        if result and result.get("district"):
            district_name = result["district"]
            # Try to match to one of our sectors
            for sector_num in range(1, 7):
                if str(sector_num) in district_name or f"Sector {sector_num}" in district_name:
                    district = District.objects.filter(name=f"Sector {sector_num}").first()
                    if district:
                        post.district = district
                        return

    # ------------------------------------------------------------------
    # Step 3: Compute District Scores
    # ------------------------------------------------------------------

    def _compute_district_scores(self):
        from interpreters.llm_summarizer import LLMSummarizer

        self.stdout.write("Computing district scores...")

        period_end = date.today()
        period_start = period_end - timedelta(days=30)

        llm = LLMSummarizer()
        llm_available = llm.is_available()

        for district in District.objects.all():
            posts = SocialPost.objects.filter(
                district=district,
                processed_at__isnull=False,
                scraped_at__date__gte=period_start,
            )

            post_count = posts.count()
            if post_count == 0:
                continue

            stats = posts.aggregate(
                avg_sentiment=Avg("sentiment_score"),
            )
            avg_sentiment = stats["avg_sentiment"] or 0.0
            issue_count = posts.filter(sentiment_label="Negative").count()

            # Per-topic breakdown
            topic_breakdown = {}
            for topic in TopicCategory.objects.all():
                topic_posts = posts.filter(topics=topic)
                t_count = topic_posts.count()
                if t_count > 0:
                    t_avg = topic_posts.aggregate(a=Avg("sentiment_score"))["a"] or 0.0
                    topic_breakdown[topic.name] = {
                        "count": t_count,
                        "avg_sentiment": round(t_avg, 4),
                    }

            # Compute overall score (0-10)
            normalized_issue = issue_count / max(post_count, 1)
            overall = (
                0.5 * ((avg_sentiment + 1) / 2) * 10  # sentiment: -1..+1 → 0..10
                + 0.3 * (1 - normalized_issue) * 10     # fewer issues = higher
                + 0.2 * min(post_count / 50, 1) * 10    # activity bonus
            )
            overall = round(max(0, min(10, overall)), 2)

            # Grade
            grade = (
                "A" if overall >= 8 else
                "B" if overall >= 6 else
                "C" if overall >= 4 else
                "D" if overall >= 2 else "F"
            )

            # LLM insight
            extra = {}
            if llm_available:
                top_topics = sorted(
                    topic_breakdown.items(),
                    key=lambda x: x[1]["count"], reverse=True
                )[:3]
                insight = llm.generate_district_insight(
                    district.name, avg_sentiment,
                    [(name, data["count"]) for name, data in top_topics],
                    post_count,
                )
                if insight:
                    extra["llm_insight"] = insight

            score_data = {
                "avg_sentiment": round(avg_sentiment, 4),
                "post_count": post_count,
                "issue_count": issue_count,
                "overall_score": overall,
                "grade": grade,
                "topic_breakdown": {**topic_breakdown, **extra},
            }

            DistrictScore.objects.update_or_create(
                district=district,
                period_start=period_start,
                period_end=period_end,
                defaults=score_data,
            )

            self.stdout.write(
                f"  {district.name}: {overall}/10 ({grade}) — {post_count} posts"
            )

        self.stdout.write(self.style.SUCCESS("District scores updated"))
