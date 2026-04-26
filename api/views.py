from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Avg, Count, Q
from django.utils import timezone
from datetime import timedelta

from apps.analytics.models import (
    SocialPost,
    District,
    DistrictScore,
    TopicCategory,
    Mood,
)
from .serializers import (
    SocialPostSerializer,
    SocialPostCreateSerializer,
    DistrictSerializer,
    DistrictScoreSerializer,
    DistrictSummarySerializer,
    SentimentTrendSerializer,
    TopicCategorySerializer,
    MoodEntrySerializer,
)


class SocialPostViewSet(viewsets.ModelViewSet):
    """CRUD + filtered queries for social posts."""

    queryset = SocialPost.objects.select_related("district").prefetch_related("topics").all()
    serializer_class = SocialPostSerializer

    def get_serializer_class(self):
        if self.action == "create":
            return SocialPostCreateSerializer
        return SocialPostSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        # Filter by source
        source = params.get("source")
        if source:
            qs = qs.filter(source=source)

        # Filter by district
        district_id = params.get("district")
        if district_id:
            qs = qs.filter(district_id=district_id)

        # Filter by sentiment
        sentiment = params.get("sentiment")
        if sentiment:
            qs = qs.filter(sentiment_label__iexact=sentiment)

        # Filter by topic
        topic = params.get("topic")
        if topic:
            qs = qs.filter(topics__name=topic)

        # Filter by date range
        date_from = params.get("date_from")
        if date_from:
            qs = qs.filter(scraped_at__date__gte=date_from)

        date_to = params.get("date_to")
        if date_to:
            qs = qs.filter(scraped_at__date__lte=date_to)

        # Search in content
        search = params.get("search")
        if search:
            qs = qs.filter(content__icontains=search)

        return qs

    @action(detail=False, methods=["get"])
    def recent(self, request):
        """Get the most recent posts (last 7 days)."""
        week_ago = timezone.now() - timedelta(days=7)
        posts = self.get_queryset().filter(scraped_at__gte=week_ago)[:50]
        serializer = self.get_serializer(posts, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def by_district(self, request):
        """Get posts grouped by district with counts."""
        district_counts = (
            self.get_queryset()
            .values("district__id", "district__name")
            .annotate(count=Count("id"), avg_sentiment=Avg("sentiment_score"))
            .order_by("-count")
        )
        return Response(list(district_counts))


class DistrictViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only endpoints for districts."""

    queryset = District.objects.all()
    serializer_class = DistrictSerializer

    @action(detail=True, methods=["get"])
    def posts(self, request, pk=None):
        """Get all posts for a specific district."""
        district = self.get_object()
        posts = SocialPost.objects.filter(district=district).order_by("-scraped_at")[:100]
        serializer = SocialPostSerializer(posts, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def scores(self, request, pk=None):
        """Get score history for a specific district."""
        district = self.get_object()
        scores = DistrictScore.objects.filter(district=district).order_by("-period_end")
        serializer = DistrictScoreSerializer(scores, many=True)
        return Response(serializer.data)


class DistrictScoreViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only endpoints for district scores."""

    queryset = DistrictScore.objects.select_related("district").all()
    serializer_class = DistrictScoreSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        district_id = self.request.query_params.get("district")
        if district_id:
            qs = qs.filter(district_id=district_id)
        return qs


class MapSummaryView(APIView):
    """Aggregated district data for the interactive map view."""

    def get(self, request):
        districts = District.objects.all()
        summaries = []

        for district in districts:
            # Get latest score
            latest_score = (
                DistrictScore.objects.filter(district=district)
                .order_by("-period_end")
                .first()
            )

            # Get top issues (most common negative topics)
            top_topics = (
                SocialPost.objects.filter(
                    district=district,
                    sentiment_label="Negative",
                )
                .values("topics__name")
                .annotate(count=Count("id"))
                .order_by("-count")[:3]
            )

            summaries.append({
                "district_id": district.id,
                "district_name": district.name,
                "overall_score": latest_score.overall_score if latest_score else 0.0,
                "grade": latest_score.grade if latest_score else "N/A",
                "post_count": latest_score.post_count if latest_score else 0,
                "avg_sentiment": latest_score.avg_sentiment if latest_score else 0.0,
                "top_issues": [t["topics__name"] for t in top_topics if t["topics__name"]],
            })

        serializer = DistrictSummarySerializer(summaries, many=True)
        return Response(serializer.data)


class SentimentTrendView(APIView):
    """Sentiment trends over time for charts."""

    def get(self, request):
        days = int(request.query_params.get("days", 30))
        district_id = request.query_params.get("district")
        source = request.query_params.get("source")

        start_date = timezone.now() - timedelta(days=days)

        qs = SocialPost.objects.filter(scraped_at__gte=start_date)
        if district_id:
            qs = qs.filter(district_id=district_id)
        if source:
            qs = qs.filter(source=source)

        trends = (
            qs.extra(select={"date": "DATE(scraped_at)"})
            .values("date")
            .annotate(
                avg_sentiment=Avg("sentiment_score"),
                post_count=Count("id"),
            )
            .order_by("date")
        )

        serializer = SentimentTrendSerializer(trends, many=True)
        return Response(serializer.data)


class TopicCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only endpoints for topic categories."""

    queryset = TopicCategory.objects.all()
    serializer_class = TopicCategorySerializer


class OverviewStatsView(APIView):
    """High-level statistics for the dashboard."""

    def get(self, request):
        total_posts = SocialPost.objects.count()
        week_ago = timezone.now() - timedelta(days=7)
        recent_posts = SocialPost.objects.filter(scraped_at__gte=week_ago).count()

        sentiment_dist = (
            SocialPost.objects.values("sentiment_label")
            .annotate(count=Count("id"))
        )

        source_dist = (
            SocialPost.objects.values("source")
            .annotate(count=Count("id"))
        )

        avg_sentiment = SocialPost.objects.aggregate(
            avg=Avg("sentiment_score")
        )["avg"] or 0.0

        return Response({
            "total_posts": total_posts,
            "recent_posts_7d": recent_posts,
            "avg_sentiment": round(avg_sentiment, 4),
            "sentiment_distribution": list(sentiment_dist),
            "source_distribution": list(source_dist),
            "districts_count": District.objects.count(),
        })


# Keep original viewset for backward compatibility
class MoodViewSet(viewsets.ModelViewSet):
    queryset = Mood.objects.all()
    serializer_class = MoodEntrySerializer

    def perform_create(self, serializer):
        serializer.save()
