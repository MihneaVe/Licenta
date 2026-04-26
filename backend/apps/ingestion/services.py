"""Ingestion orchestration: paste → parse → normalize → persist → payload.

The :class:`IngestionResult.payload` field is the contract with the NLP
side: it contains exactly what
``interpreters.mood_analyzer.MoodAnalyzer.analyze`` expects (the cleaned
``content`` text, plus the database ``post_id`` so the analyzer can write
results back).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from django.db import transaction
from django.utils.dateparse import parse_datetime

from apps.analytics.models import SocialPost

from .normalizer import NormalizedText, normalize
from .parsers import ParsedPost, parse


# Source values used by SocialPost.SOURCE_CHOICES — pasted X posts are
# stored under "reddit" / "facebook" today, so we map to a stable string
# the model already accepts. X is mapped to "reddit" → too lossy; instead
# we store under its own value and let the migration accept it. The
# SocialPost model itself uses choices, but Django only enforces those at
# the form level — DB column is plain VARCHAR(20).
SOURCE_DB_VALUE = {
    "reddit": "reddit",
    "x": "x",
}


class IngestionError(ValueError):
    """Raised when ingestion is rejected (empty/duplicate/unsupported)."""


@dataclass
class IngestionResult:
    """Return value of :func:`ingest_post`. ``payload`` is NLP-pipeline-ready."""

    post_id: int
    source: str
    created: bool
    parsed: ParsedPost
    normalized: NormalizedText
    payload: dict = field(default_factory=dict)


def _stable_source_id(source: str, content_clean: str) -> str:
    """Deterministic synthetic ID when the source didn't supply one.

    Used to deduplicate identical pastes and to satisfy the
    ``unique_together = (source, source_id)`` constraint on
    :class:`SocialPost`.
    """
    digest = hashlib.sha1(content_clean.encode("utf-8")).hexdigest()[:16]
    return f"manual_{digest}"


def _coerce_original_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return parse_datetime(value)


@transaction.atomic
def ingest_post(source: str, raw_text: str) -> IngestionResult:
    """Parse and persist a single pasted post.

    Returns an :class:`IngestionResult` whose ``payload`` field is the
    clean dict the NLP pipeline consumes. ``created=False`` means the
    same content was already ingested (idempotent re-paste); the existing
    row is returned untouched.

    Raises :class:`IngestionError` if input is empty after normalization
    or the source is unsupported.
    """
    parsed = parse(source, raw_text)
    if parsed.is_empty():
        raise IngestionError("Input is empty.")

    normalized = normalize(parsed.content_raw)
    if normalized.is_empty:
        raise IngestionError("Nothing left after cleaning the input.")

    source_db = SOURCE_DB_VALUE.get(parsed.source)
    if source_db is None:
        raise IngestionError(f"Unsupported source: {parsed.source!r}.")

    source_id = parsed.source_id or _stable_source_id(source_db, normalized.clean)

    extra = {
        **(parsed.extra or {}),
        "raw_paste": raw_text,
        "ingestion": {
            "method": "manual_paste",
            "removed_urls": normalized.removed_urls,
            "removed_mentions": normalized.removed_mentions,
            "removed_hashtags": normalized.removed_hashtags,
            "char_count": normalized.char_count,
            "word_count": normalized.word_count,
        },
    }

    defaults = {
        "content": normalized.clean,
        "author": parsed.author,
        "url": parsed.url,
        "score": parsed.score,
        "extra_data": extra,
        "original_date": _coerce_original_date(parsed.original_date),
        "ingestion_method": "manual_paste",
        # processed_at intentionally left NULL — the NLP pipeline's
        # `--process-only` step will pick this row up next run.
    }

    post, created = SocialPost.objects.get_or_create(
        source=source_db,
        source_id=source_id,
        defaults=defaults,
    )

    if not created:
        # Re-paste of the same content: refresh metadata in case the user
        # corrected author/url, but never overwrite NLP results.
        dirty = False
        for field_name in ("author", "url", "score", "original_date"):
            new_val = defaults[field_name]
            if new_val and getattr(post, field_name) != new_val:
                setattr(post, field_name, new_val)
                dirty = True
        if dirty:
            post.save(update_fields=["author", "url", "score", "original_date"])

    payload = {
        "post_id": post.id,
        "source": source_db,
        "source_id": source_id,
        "content": normalized.clean,
        "author": parsed.author,
        "url": parsed.url,
        "score": parsed.score,
        "original_date": parsed.original_date,
        "metadata": parsed.extra,
        "ready_for_nlp": True,
    }

    return IngestionResult(
        post_id=post.id,
        source=source_db,
        created=created,
        parsed=parsed,
        normalized=normalized,
        payload=payload,
    )
