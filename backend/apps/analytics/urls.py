from django.urls import path

from .views import feed_view, sentiment_stats_json


app_name = "analytics"

urlpatterns = [
    path("", feed_view, name="feed"),
    path("stats/sentiment.json", sentiment_stats_json, name="sentiment_stats"),
]
