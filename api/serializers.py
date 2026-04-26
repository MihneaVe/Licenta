from rest_framework import serializers
from backend.apps.analytics.models import (
    SocialPost,
    District,
    DistrictScore,
    TopicCategory,
    Mood,
)
from backend.apps.users.models import User


class TopicCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TopicCategory
        fields = ["id", "name", "description"]


class DistrictSerializer(serializers.ModelSerializer):
    post_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = District
        fields = ["id", "name", "city", "boundary_geojson", "post_count"]


class SocialPostSerializer(serializers.ModelSerializer):
    district_name = serializers.CharField(source="district.name", read_only=True, default="")
    topics = TopicCategorySerializer(many=True, read_only=True)

    class Meta:
        model = SocialPost
        fields = [
            "id", "source", "source_id", "content", "author", "url",
            "latitude", "longitude", "location_name",
            "district", "district_name",
            "sentiment_score", "sentiment_label",
            "topics", "topic_scores",
            "score", "extra_data",
            "language", "original_date", "scraped_at", "processed_at",
        ]
        read_only_fields = [
            "sentiment_score", "sentiment_label", "topic_scores",
            "scraped_at", "processed_at",
        ]


class SocialPostCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating posts (from scraper ingestion)."""

    class Meta:
        model = SocialPost
        fields = [
            "source", "source_id", "content", "author", "url",
            "latitude", "longitude", "location_name",
            "district", "score", "extra_data", "language", "original_date",
        ]


class DistrictScoreSerializer(serializers.ModelSerializer):
    district_name = serializers.CharField(source="district.name", read_only=True)

    class Meta:
        model = DistrictScore
        fields = [
            "id", "district", "district_name",
            "period_start", "period_end",
            "avg_sentiment", "post_count", "issue_count",
            "overall_score", "grade",
            "topic_breakdown", "computed_at",
        ]


class DistrictSummarySerializer(serializers.Serializer):
    """Lightweight district summary for the map view."""

    district_id = serializers.IntegerField()
    district_name = serializers.CharField()
    overall_score = serializers.FloatField()
    grade = serializers.CharField()
    post_count = serializers.IntegerField()
    avg_sentiment = serializers.FloatField()
    top_issues = serializers.ListField(child=serializers.CharField())


class SentimentTrendSerializer(serializers.Serializer):
    """Sentiment trend data point for charts."""

    date = serializers.DateField()
    avg_sentiment = serializers.FloatField()
    post_count = serializers.IntegerField()


# Keep original serializer for backward compatibility
class MoodEntrySerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = Mood
        fields = ["id", "user", "mood_type", "intensity", "created_at"]
