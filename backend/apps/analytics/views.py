from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.shortcuts import render

from .models import District, SocialPost


def feed_view(request):
    """Resident-facing feed of all ingested civic posts (real DB rows).

    Replaces the legacy mock mood form. Posts are rendered with the
    LLM-extracted title (when available), the original/cleaned author,
    the source badge, and the assigned district.

    Query params:
        ?source=reddit|x   filter by platform
        ?district=<id>     filter by district
        ?q=<text>          full-text search in content
    """
    qs = (
        SocialPost.objects
        .select_related("district")
        .order_by("-original_date", "-scraped_at")
    )

    source = request.GET.get("source")
    if source in ("reddit", "x"):
        qs = qs.filter(source=source)

    district_id = request.GET.get("district")
    if district_id and district_id.isdigit():
        qs = qs.filter(district_id=int(district_id))

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(content__icontains=q)

    posts = list(qs[:200])

    # Decorate each row with the LLM title (if present) and a body excerpt.
    for p in posts:
        extra = p.extra_data or {}
        p.display_title = (extra.get("title") or "").strip() or _fallback_title(p.content)
        p.title_was_generated = bool(extra.get("llm_title_generated"))
        p.body_excerpt = _excerpt(p.content, 360)

    districts = District.objects.annotate(post_count=Count("posts")).order_by("name")

    summary = SocialPost.objects.aggregate(
        total=Count("id"),
        avg_sent=Avg("sentiment_score"),
    )

    return render(request, "analytics/feed.html", {
        "posts": posts,
        "districts": districts,
        "summary": summary,
        "active_source": source or "",
        "active_district": int(district_id) if district_id and district_id.isdigit() else None,
        "search_query": q,
    })


def _excerpt(text: str, limit: int) -> str:
    if not text:
        return ""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def _fallback_title(content: str) -> str:
    """When neither parser nor LLM gave us a title, use the first sentence."""
    if not content:
        return "(fără titlu)"
    head = content.strip().split(".", 1)[0].strip()
    if len(head) > 80:
        head = head[:80].rsplit(" ", 1)[0] + "…"
    return head or "(fără titlu)"


def sentiment_stats_json(request):
    """Lightweight JSON endpoint kept for backward compat with old JS."""
    stats = (
        SocialPost.objects.values("sentiment_label")
        .annotate(count=Count("id"))
    )
    return JsonResponse(list(stats), safe=False)


def map_view(request):
    """Leaflet map of Bucharest quarters with per-quarter post counts."""
    return render(request, "analytics/map.html", {})


def quarters_geojson(request):
    """``/feed/api/quarters.geojson`` — feeds the Leaflet map.

    Returns one GeoJSON Feature per Bucharest district that has either
    a centroid or a boundary polygon. Each feature carries ``post_count``
    and ``avg_sentiment`` so the client can colour-code without a second
    round-trip.
    """
    qs = (
        District.objects
        .annotate(
            post_count=Count("posts"),
            avg_sentiment=Avg("posts__sentiment_score"),
        )
        .filter(
            Q(centroid_lat__isnull=False) | Q(boundary_geojson__isnull=False)
        )
        .order_by("kind", "name")
    )

    features = []
    for d in qs:
        if d.boundary_geojson:
            geometry = d.boundary_geojson
        elif d.centroid_lat is not None and d.centroid_lng is not None:
            # GeoJSON expects [lng, lat] order.
            geometry = {
                "type": "Point",
                "coordinates": [d.centroid_lng, d.centroid_lat],
            }
        else:
            continue

        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "id": d.id,
                "name": d.name,
                "kind": d.kind,
                "parent": d.parent.name if d.parent else None,
                "post_count": d.post_count,
                "avg_sentiment": (
                    round(d.avg_sentiment, 4) if d.avg_sentiment is not None else None
                ),
            },
        })

    return JsonResponse(
        {
            "type": "FeatureCollection",
            "features": features,
        }
    )
