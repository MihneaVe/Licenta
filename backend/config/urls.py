from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView


urlpatterns = [
    path('admin/', admin.site.urls),

    # REST API (analytics + ingestion live here too as `/api/ingest/`).
    path('api/', include('api.endpoints')),

    # Manual paste UI — replaces the legacy mock-mood dashboard.
    path('ingest/', include('apps.ingestion.urls', namespace='ingestion')),

    # Old entry points point at the new ingestion page so existing
    # bookmarks keep working.
    path('', RedirectView.as_view(pattern_name='ingestion:paste', permanent=False), name='index'),
    path('dashboard/', RedirectView.as_view(pattern_name='ingestion:paste', permanent=False), name='dashboard'),
]
