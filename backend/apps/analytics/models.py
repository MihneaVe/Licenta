from django.db import models


class District(models.Model):
    """A geographic unit posts get assigned to.

    The single ``District`` table now models three nested kinds:

    * ``city``    — the municipality itself (București), default fallback.
    * ``sector``  — Bucharest's six administrative sectors (Sector 1–6).
    * ``quarter`` — traditional neighborhoods / cartiere (Aviației,
      Băneasa, Crângași, Drumul Taberei, ~70 of them in total).

    Quarters point at their parent sector via :attr:`parent`. The
    optional ``boundary_geojson`` polygon and ``centroid_lat/lng``
    centroid feed the Leaflet map view.
    """

    KIND_CHOICES = [
        ("city", "City"),
        ("sector", "Sector"),
        ("quarter", "Quarter"),
    ]

    name = models.CharField(max_length=100, unique=True)
    city = models.CharField(max_length=100, default="București")
    kind = models.CharField(
        max_length=10, choices=KIND_CHOICES, default="sector",
        help_text="Hierarchy level — city → sector → quarter.",
    )
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="children",
        help_text="Parent geographic unit (e.g. a quarter's sector).",
    )
    boundary_geojson = models.JSONField(
        blank=True, null=True,
        help_text="GeoJSON polygon/multipolygon for the district boundary.",
    )
    centroid_lat = models.FloatField(null=True, blank=True)
    centroid_lng = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["kind", "name"]
        indexes = [
            models.Index(fields=["kind"]),
            models.Index(fields=["parent"]),
        ]

    def __str__(self):
        return f"{self.name}, {self.city}"


class TopicCategory(models.Model):
    """Civic issue category (e.g. infrastructure, cleanliness, safety)."""

    CATEGORY_CHOICES = [
        ("infrastructure", "Infrastructure"),
        ("cleanliness", "Cleanliness"),
        ("safety", "Safety"),
        ("transport", "Transport"),
        ("greenspace", "Green Spaces"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=50, unique=True, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Topic categories"

    def __str__(self):
        return self.get_name_display()


class SocialPost(models.Model):
    """A scraped social media post with NLP analysis results."""

    SOURCE_CHOICES = [
        ("reddit", "Reddit"),
        ("x", "X (Twitter)"),
        ("google_maps", "Google Maps"),
        ("facebook", "Facebook Groups"),
    ]

    INGESTION_METHODS = [
        ("scraper", "Automated scraper"),
        ("manual_paste", "Manual paste (ingestion module)"),
    ]

    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    source_id = models.CharField(
        max_length=255, blank=True,
        help_text="Original post ID from the source platform",
    )
    content = models.TextField()
    author = models.CharField(max_length=255, blank=True)
    url = models.URLField(blank=True)

    # Geo fields
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    location_name = models.CharField(max_length=255, blank=True)
    district = models.ForeignKey(
        District, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="posts",
    )

    # NLP analysis results
    sentiment_score = models.FloatField(
        null=True, blank=True,
        help_text="Sentiment score from -1.0 (negative) to +1.0 (positive)",
    )
    sentiment_label = models.CharField(
        max_length=20, blank=True,
        help_text="Positive, Negative, or Neutral",
    )
    topics = models.ManyToManyField(TopicCategory, blank=True, related_name="posts")
    topic_scores = models.JSONField(
        blank=True, null=True,
        help_text="Dict of topic_name -> confidence score",
    )

    # Source-specific metadata
    score = models.IntegerField(default=0, help_text="Upvotes/reactions/rating")
    extra_data = models.JSONField(
        blank=True, null=True,
        help_text="Additional source-specific data",
    )

    # Language
    language = models.CharField(max_length=10, blank=True, default="ro")

    # How this row entered the system. Lets the dashboard distinguish
    # scraped vs. manually-pasted content for the evaluation chapter.
    ingestion_method = models.CharField(
        max_length=20, choices=INGESTION_METHODS,
        default="scraper",
    )

    # Timestamps
    original_date = models.DateTimeField(
        null=True, blank=True,
        help_text="Original post creation date from the source",
    )
    scraped_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-scraped_at"]
        indexes = [
            models.Index(fields=["source", "source_id"]),
            models.Index(fields=["district"]),
            models.Index(fields=["sentiment_label"]),
            models.Index(fields=["-scraped_at"]),
        ]
        unique_together = [["source", "source_id"]]

    def __str__(self):
        preview = self.content[:80] + "..." if len(self.content) > 80 else self.content
        return f"[{self.source}] {preview}"


class DistrictScore(models.Model):
    """Aggregated sentiment and issue scores per district, computed periodically."""

    district = models.ForeignKey(
        District, on_delete=models.CASCADE, related_name="scores",
    )
    period_start = models.DateField()
    period_end = models.DateField()

    # Aggregated metrics
    avg_sentiment = models.FloatField(
        help_text="Average sentiment score across all posts in this period",
    )
    post_count = models.IntegerField(default=0)
    issue_count = models.IntegerField(
        default=0,
        help_text="Number of posts with negative sentiment",
    )
    overall_score = models.FloatField(
        help_text="Combined district score (0–10 scale)",
    )
    grade = models.CharField(
        max_length=2, blank=True,
        help_text="Letter grade A–F",
    )

    # Per-topic breakdown
    topic_breakdown = models.JSONField(
        blank=True, null=True,
        help_text="Dict of topic_name -> {count, avg_sentiment}",
    )

    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_end", "district"]
        unique_together = [["district", "period_start", "period_end"]]

    def __str__(self):
        return f"{self.district.name}: {self.overall_score:.1f} ({self.grade})"


# Keep the original Mood model for backward compatibility
class Mood(models.Model):
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    mood_type = models.CharField(max_length=50)
    intensity = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.mood_type} ({self.intensity})"
