"""Common types for paste parsers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


class ParserError(ValueError):
    """Raised when paste input is malformed or the source is unknown."""


@dataclass
class ParsedPost:
    """Structured fields extracted from a raw paste, ready for normalization.

    ``content_raw`` is the title+body text concatenation that will be fed to
    the text normalizer. The other fields populate :class:`SocialPost`
    columns directly (no further parsing needed).
    """

    source: str
    content_raw: str
    source_id: str = ""
    author: str = ""
    url: str = ""
    score: int = 0
    original_date: Optional[str] = None  # ISO 8601, optional
    extra: dict = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not self.content_raw or not self.content_raw.strip()
