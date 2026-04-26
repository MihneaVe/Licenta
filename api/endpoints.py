from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SocialPostViewSet,
    DistrictViewSet,
    DistrictScoreViewSet,
    TopicCategoryViewSet,
    MoodViewSet,
    MapSummaryView,
    SentimentTrendView,
    OverviewStatsView,
)

router = DefaultRouter()
router.register(r"posts", SocialPostViewSet, basename="socialpost")
router.register(r"districts", DistrictViewSet, basename="district")
router.register(r"scores", DistrictScoreViewSet, basename="districtscore")
router.register(r"topics", TopicCategoryViewSet, basename="topiccategory")
router.register(r"moods", MoodViewSet, basename="mood")

urlpatterns = [
    # DRF router endpoints
    path("", include(router.urls)),

    # Custom aggregate endpoints
    path("map/summary/", MapSummaryView.as_view(), name="map_summary"),
    path("trends/sentiment/", SentimentTrendView.as_view(), name="sentiment_trends"),
    path("stats/overview/", OverviewStatsView.as_view(), name="overview_stats"),
]
