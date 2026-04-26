from django.contrib import admin
from .models import SocialPost, District, DistrictScore, TopicCategory, Mood


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "created_at")
    search_fields = ("name", "city")


@admin.register(TopicCategory)
class TopicCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description")


@admin.register(SocialPost)
class SocialPostAdmin(admin.ModelAdmin):
    list_display = ("source", "content_preview", "sentiment_label", "district", "scraped_at")
    list_filter = ("source", "sentiment_label", "district")
    search_fields = ("content", "location_name", "author")
    readonly_fields = ("scraped_at", "processed_at")

    def content_preview(self, obj):
        return obj.content[:100] + "..." if len(obj.content) > 100 else obj.content
    content_preview.short_description = "Content"


@admin.register(DistrictScore)
class DistrictScoreAdmin(admin.ModelAdmin):
    list_display = ("district", "overall_score", "grade", "post_count", "period_end")
    list_filter = ("district", "grade")


@admin.register(Mood)
class MoodAdmin(admin.ModelAdmin):
    list_display = ("user", "mood_type", "intensity", "created_at")
    search_fields = ("user__username", "mood_type")
    list_filter = ("mood_type",)
