from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'bio', 'location', 'birth_date')
    search_fields = ('user__username', 'bio', 'location')
    list_filter = ('location', 'birth_date')