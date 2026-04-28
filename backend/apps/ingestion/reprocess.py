"""Re-process already-stored ``SocialPost`` rows with the local LLM.

For each row:

1. Re-extract ``title`` / ``body`` / ``author`` / ``date`` from the
   original raw paste using :class:`LLMExtractor`. The deterministic
   parsers leave a lot of noise behind (Reddit pastes get title="•",
   X pastes have authors fused into the body, dates as "18 mar.").
2. Generate a title with the LLM if one is still missing afterwards.
3. Update the DB row with the cleaned values, mark
   ``extra_data['llm_processed']=True`` so we don't redo work on the
   next pass, and assign the post to the București district (or to a
   specific sector if the LLM saw "Sectorul 4" etc. in the text).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date as date_cls, datetime, timezone
from typing import Optional

from django.db import transaction
from django.utils.dateparse import parse_datetime

from apps.analytics.models import District, SocialPost

from .llm_extractor import ExtractedFields, LLMExtractor


logger = logging.getLogger(__name__)


BUCHAREST_DISTRICT_NAME = "București"
SECTOR_DISTRICT_TEMPLATE = "Sector {n}"
DEFAULT_CITY = "București"


def _load_quarter_lookup() -> dict[str, District]:
    """Map canonical quarter names → District objects (one query)."""
    return {
        d.name: d
        for d in District.objects.filter(kind="quarter")
    }


@dataclass
class ReprocessResult:
    post_id: int
    changed: bool
    title_generated: bool
    fields: ExtractedFields
    district_name: str
    skipped_reason: str = ""


def ensure_bucharest_districts() -> dict[str, District]:
    """Create București (city-level) + Sector 1..6 if they don't exist.

    Returns a dict keyed by district name for quick lookup by the
    re-process loop.
    """
    names = [BUCHAREST_DISTRICT_NAME] + [
        SECTOR_DISTRICT_TEMPLATE.format(n=n) for n in range(1, 7)
    ]
    districts: dict[str, District] = {}
    for name in names:
        obj, _ = District.objects.get_or_create(
            name=name, defaults={"city": DEFAULT_CITY}
        )
        districts[name] = obj
    return districts


def reprocess_post(
    post: SocialPost,
    extractor: LLMExtractor,
    districts: dict[str, District],
    quarters: dict[str, District] | None = None,
    *,
    force: bool = False,
    assign_default_to_bucharest: bool = True,
) -> ReprocessResult:
    """Run LLM extraction + title generation + district assignment on one row.

    Args:
        post: The :class:`SocialPost` row to update.
        extractor: A constructed :class:`LLMExtractor` (re-using one
            keeps the model warm in Ollama).
        districts: Output of :func:`ensure_bucharest_districts`.
        force: Re-process even if ``extra_data['llm_processed']`` is True.
        assign_default_to_bucharest: When the LLM doesn't report a
            specific sector, fall back to the city-level București
            district.
    """
    extra = dict(post.extra_data or {})
    if extra.get("llm_processed") and not force:
        return ReprocessResult(
            post_id=post.id,
            changed=False,
            title_generated=False,
            fields=ExtractedFields(),
            district_name=post.district.name if post.district else "",
            skipped_reason="already llm_processed",
        )

    # Prefer the original raw paste — it has all the context the
    # deterministic parser threw away. Fall back to the cleaned content.
    raw_source = extra.get("raw_paste") or post.content or ""
    existing_title = (extra.get("title") or "").strip()
    # The deterministic Reddit parser sets bogus titles like "•" or
    # "Go to bucuresti" — treat those as "no title" for the LLM.
    if existing_title in ("", "•", "Go to bucuresti"):
        existing_title = ""

    fields = extractor.extract(raw_source, post.source, existing_title=existing_title)

    title = fields.title
    title_generated = False
    if not title:
        title = extractor.generate_title(fields.body or post.content)
        title_generated = bool(title)
        fields.title = title  # so callers can read the final title off `fields`
        fields.title_was_generated = title_generated

    # Apply changes.
    changed = False

    # Body / content
    if fields.body and fields.body != post.content:
        post.content = fields.body
        changed = True

    # Author — only overwrite if we have one and the existing value is empty
    # OR is a generic placeholder (the X parser sometimes captured @handle
    # noise that the LLM can correct).
    if fields.author and fields.author != post.author:
        if not post.author or post.source == "reddit":
            post.author = fields.author
            changed = True

    # Date
    if fields.date_iso and not post.original_date:
        parsed_date = parse_datetime(fields.date_iso)
        if parsed_date:
            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=timezone.utc)
            post.original_date = parsed_date
            changed = True

    # District — quarter > sector > city precedence.
    chosen_district: Optional[District] = None
    if fields.mentioned_quarter and quarters:
        chosen_district = quarters.get(fields.mentioned_quarter)
    if chosen_district is None and fields.mentioned_sector and 1 <= fields.mentioned_sector <= 6:
        chosen_district = districts.get(
            SECTOR_DISTRICT_TEMPLATE.format(n=fields.mentioned_sector)
        )
    if chosen_district is None and assign_default_to_bucharest:
        chosen_district = districts.get(BUCHAREST_DISTRICT_NAME)
    if chosen_district and post.district_id != chosen_district.id:
        post.district = chosen_district
        changed = True

    # Location hint
    if fields.location_hint and not post.location_name:
        post.location_name = fields.location_hint[:255]
        changed = True

    # Stash everything new into extra_data.
    extra["title"] = title
    extra["llm_processed"] = True
    extra["llm_processed_at"] = datetime.now(timezone.utc).isoformat()
    extra["llm_model"] = extractor.model
    extra["llm_title_generated"] = title_generated
    if fields.location_hint:
        extra["llm_location_hint"] = fields.location_hint
    if fields.mentioned_sector:
        extra["llm_mentioned_sector"] = fields.mentioned_sector
    if fields.mentioned_quarter:
        extra["llm_mentioned_quarter"] = fields.mentioned_quarter
    post.extra_data = extra

    post.save()

    return ReprocessResult(
        post_id=post.id,
        changed=changed,
        title_generated=title_generated,
        fields=fields,
        district_name=chosen_district.name if chosen_district else "",
    )


def reprocess_all(
    *,
    extractor: Optional[LLMExtractor] = None,
    force: bool = False,
    limit: Optional[int] = None,
    only_ids: Optional[list[int]] = None,
) -> list[ReprocessResult]:
    """Convenience wrapper for the management command and the API.

    Picks up every ``SocialPost`` (optionally filtered/limited) and runs
    :func:`reprocess_post` against each one, sharing a single warm
    Ollama session for speed.
    """
    extractor = extractor or LLMExtractor()
    if not extractor.is_available():
        raise RuntimeError(
            f"Ollama model {extractor.model!r} is not reachable at "
            f"{extractor.host}. Start Ollama and `ollama pull {extractor.model}`."
        )

    districts = ensure_bucharest_districts()
    quarters = _load_quarter_lookup()

    qs = SocialPost.objects.all().order_by("id")
    if only_ids:
        qs = qs.filter(id__in=only_ids)
    if limit:
        qs = qs[:limit]

    results: list[ReprocessResult] = []
    # Iterate via a list so we don't hold a server-side cursor open
    # for the whole LLM run (Supabase pooler kills idle connections).
    # We deliberately do NOT wrap each iteration in transaction.atomic:
    # the slow LLM call inside reprocess_post would keep a Supabase
    # session open past the 8s statement timeout. post.save() is a
    # single UPDATE — atomic at the DB level by itself.
    posts = list(qs)
    for post in posts:
        try:
            result = reprocess_post(
                post, extractor, districts, quarters, force=force,
            )
            results.append(result)
        except Exception as exc:  # noqa: BLE001 — we want the loop to keep going
            logger.exception("Reprocess failed for post %s: %s", post.id, exc)
            results.append(
                ReprocessResult(
                    post_id=post.id,
                    changed=False,
                    title_generated=False,
                    fields=ExtractedFields(),
                    district_name="",
                    skipped_reason=f"error: {exc}",
                )
            )
    return results
