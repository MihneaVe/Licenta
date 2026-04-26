"""Source-specific paste parsers.

Each parser turns a raw copy-paste blob into a :class:`ParsedPost`. They
are best-effort — when no metadata can be extracted, the entire input is
treated as the post body.
"""

from .base import ParsedPost, ParserError
from .reddit import parse_reddit
from .x import parse_x


SUPPORTED_SOURCES = ("reddit", "x")


def parse(source: str, raw_text: str) -> ParsedPost:
    """Dispatch to the parser for ``source`` (case-insensitive).

    Raises :class:`ParserError` if ``source`` is unknown.
    """
    src = (source or "").strip().lower()
    if src == "reddit":
        return parse_reddit(raw_text)
    if src in ("x", "twitter"):
        return parse_x(raw_text)
    raise ParserError(f"Unsupported source: {source!r}. Expected one of {SUPPORTED_SOURCES}.")


__all__ = [
    "ParsedPost",
    "ParserError",
    "SUPPORTED_SOURCES",
    "parse",
    "parse_reddit",
    "parse_x",
]
