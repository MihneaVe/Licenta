from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView


urlpatterns = [
    path('admin/', admin.site.urls),

    # REST API (analytics queries + ingestion endpoint).
    path('api/', include('api.endpoints')),

    # Resident-facing feed of real ingested posts.
    path('feed/', include('apps.analytics.urls', namespace='analytics')),

    # Manual paste UI for adding new posts.
    path('ingest/', include('apps.ingestion.urls', namespace='ingestion')),

    # Old entry points keep working — both land on the live feed now,
    # which is the natural homepage for residents.
    path('', RedirectView.as_view(pattern_name='analytics:feed', permanent=False), name='index'),
    path('dashboard/', RedirectView.as_view(pattern_name='analytics:feed', permanent=False), name='dashboard'),
]
