from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.endpoints')),
    path('analytics/', include('apps.analytics.urls')),
    path('auth/', include('apps.authentication.urls')),
    path('users/', include('apps.users.urls')),
    path('', include('apps.core.urls')),
]
