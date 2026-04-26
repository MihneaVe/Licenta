from django.urls import path

from .views import IngestAPIView, paste_page


app_name = "ingestion"

urlpatterns = [
    path("", paste_page, name="paste"),
    path("api/", IngestAPIView.as_view(), name="api"),
]
