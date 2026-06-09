"""Ingestion: paste → parse → normalize → persist (SQLAlchemy).

Idempotent on (source, source_id): re-pasting the same content updates metadata
but never overwrites NLP results. Mirrors the former Django services.ingest_post.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..db import SessionLocal
from ..models import SocialPost
from .normalizer import normalize
from .parsers import parse

SOURCE_DB_VALUE = {"reddit": "reddit", "x": "x"}


class IngestionError(ValueError):
    """Raised when ingestion is rejected (empty / unsupported)."""


@dataclass
class IngestionResult:
    post_id: int
    source: str
    created: bool
    content: str


def _stable_source_id(content_clean: str) -> str:
    digest = hashlib.sha1(content_clean.encode("utf-8")).hexdigest()[:16]
    return f"manual_{digest}"


def ingest_post(source: str, raw_text: str) -> IngestionResult:
    parsed = parse(source, raw_text)
    if parsed.is_empty():
        raise IngestionError("Input is empty.")

    normalized = normalize(parsed.content_raw)
    if normalized.is_empty:
        raise IngestionError("Nothing left after cleaning the input.")

    source_db = SOURCE_DB_VALUE.get(parsed.source)
    if source_db is None:
        raise IngestionError(f"Unsupported source: {parsed.source!r}.")

    source_id = parsed.source_id or _stable_source_id(normalized.clean)
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

    with SessionLocal() as s:
        existing = s.scalar(
            select(SocialPost).where(
                SocialPost.source == source_db, SocialPost.source_id == source_id
            )
        )
        if existing:
            dirty = False
            for attr, val in (("author", parsed.author), ("url", parsed.url), ("score", parsed.score)):
                if val and getattr(existing, attr) != val:
                    setattr(existing, attr, val)
                    dirty = True
            if dirty:
                s.commit()
            return IngestionResult(existing.id, source_db, False, normalized.clean)

        post = SocialPost(
            source=source_db,
            source_id=source_id,
            content=normalized.clean,
            author=parsed.author or "",
            url=parsed.url or "",
            score=parsed.score or 0,
            extra_data=extra,
            ingestion_method="manual_paste",
        )
        s.add(post)
        s.commit()
        s.refresh(post)
        return IngestionResult(post.id, source_db, True, normalized.clean)
