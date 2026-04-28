from django.urls import path

from .views import (
    feed_view,
    map_view,
    quarters_geojson,
    sentiment_stats_json,
)


app_name = "analytics"

urlpatterns = [
    path("", feed_view, name="feed"),
    path("map/", map_view, name="map"),
    path("api/quarters.geojson", quarters_geojson, name="quarters_geojson"),
    path("stats/sentiment.json", sentiment_stats_json, name="sentiment_stats"),
]
