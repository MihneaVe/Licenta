"""Parser for X / Twitter copy-paste input.

Handles two input shapes:

1. **Web copy-paste** — the layout you get when selecting a tweet on
   ``x.com``: display name, ``@handle``, timestamp, body text, then
   engagement metrics (replies, reposts, likes, views).
2. **Plain text** — anything else; treated as the tweet body.

The web layout is recognised by anchoring on the ``@handle`` line: the
line immediately before it is the display name, the lines after it (up
to the body) carry timestamp/verification glyphs, and trailing engagement
metrics are stripped from the end.
"""

from __future__ import annotations

import re
from typing import Optional

from .base import ParsedPost


HANDLE_LINE_RE = re.compile(r"^@([A-Za-z0-9_]{1,15})\s*$")
HANDLE_INLINE_RE = re.compile(r"@([A-Za-z0-9_]{1,15})")
STATUS_URL_RE = re.compile(
    r"https?://(?:www\.|mobile\.)?(?:twitter|x)\.com/([A-Za-z0-9_]{1,15})/status/(\d+)",
    flags=re.IGNORECASE,
)
TIMESTAMP_LINE_RE = re.compile(
    r"^("
    r"\d{1,2}:\d{2}\s*(AM|PM)?(\s*·.*)?"
    r"|\d{1,2}\s*[smhd]"
    r"|(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}.*"
    r"|·.*"
    r")$",
    flags=re.IGNORECASE,
)
# A single engagement metric token: "12 Replies", "1.2K Views", "5 Reposts".
METRIC_TOKEN_RE = re.compile(
    r"\d+(\.\d+)?[kKmM]?\s*(replies?|reposts?|likes?|views?|bookmarks?|quotes?)",
    flags=re.IGNORECASE,
)
# A line that is ONLY engagement metrics (any number of them, any order).
METRIC_LINE_RE = re.compile(
    r"^\s*(?:" + METRIC_TOKEN_RE.pattern + r"\s*)+$",
    flags=re.IGNORECASE,
)


def parse_x(raw_text: str) -> ParsedPost:
    if raw_text is None:
        return ParsedPost(source="x", content_raw="")

    text = raw_text.strip()
    if not text:
        return ParsedPost(source="x", content_raw="")

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    handle = ""
    source_id = ""
    url = ""

    # Status URL is unambiguous — pull it out wherever it appears.
    for line in lines:
        m = STATUS_URL_RE.search(line)
        if m:
            handle = handle or m.group(1)
            source_id = m.group(2)
            url = m.group(0)
            break

    handle_idx: Optional[int] = None
    for i, line in enumerate(lines):
        m = HANDLE_LINE_RE.match(line)
        if m:
            handle = handle or m.group(1)
            handle_idx = i
            break

    if handle_idx is not None:
        # Web paste: drop display name (line before @handle), the handle
        # line itself, and any timestamp lines that immediately follow.
        body_start = handle_idx + 1
        while body_start < len(lines) and TIMESTAMP_LINE_RE.match(lines[body_start]):
            body_start += 1

        body_lines = lines[body_start:]
        # Strip trailing metric lines (and the status URL if it was tacked
        # on at the bottom of the paste).
        while body_lines and (
            METRIC_LINE_RE.match(body_lines[-1])
            or STATUS_URL_RE.fullmatch(body_lines[-1])
        ):
            body_lines.pop()

        body = " ".join(body_lines).strip()
        input_format = "web_paste"
    else:
        # Plain-text paste: keep all lines, just drop pure-metric lines.
        body_lines = [
            ln for ln in lines
            if not METRIC_LINE_RE.match(ln) and not STATUS_URL_RE.fullmatch(ln)
        ]
        body = " ".join(body_lines).strip()
        input_format = "plain"

    if not body:
        body = text

    if not handle:
        m_inline = HANDLE_INLINE_RE.search(body)
        if m_inline:
            handle = m_inline.group(1)

    return ParsedPost(
        source="x",
        content_raw=body,
        source_id=source_id,
        author=handle,
        url=url,
        extra={"input_format": input_format},
    )
