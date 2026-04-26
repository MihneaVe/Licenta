from django.contrib import admin
from .models import Profile, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "created_at")
    search_fields = ("username", "email")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "bio")
    search_fields = ("user__username", "bio")
