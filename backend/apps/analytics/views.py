from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Count, Avg
from .models import SocialPost, District, DistrictScore


def mood_overview(request):
    posts = SocialPost.objects.select_related("district").all()[:100]
    return render(request, 'analytics/mood_overview.html', {'posts': posts})


def mood_statistics(request):
    sentiment_stats = (
        SocialPost.objects.values("sentiment_label")
        .annotate(count=Count("id"))
    )
    return JsonResponse(list(sentiment_stats), safe=False)


def district_overview(request):
    districts = District.objects.annotate(
        post_count=Count("posts"),
        avg_sentiment=Avg("posts__sentiment_score"),
    )
    return render(request, 'analytics/district_overview.html', {
        'districts': districts,
    })
