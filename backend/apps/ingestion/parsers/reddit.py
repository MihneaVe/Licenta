"""Parser for Reddit copy-paste input.

Handles three input shapes, in order:

1. **JSON** — output of ``https://reddit.com/r/<sub>/comments/<id>.json``
   or a PRAW ``submission.__dict__`` dump.
2. **Web copy-paste** — the layout you get when selecting a post on
   ``reddit.com``: header lines (``r/foo``, ``Posted by u/bar • 5h``),
   then the title, then the body, then vote/comment counts.
3. **Plain text** — anything else; treated entirely as the post body.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Optional

from .base import ParsedPost


SUBREDDIT_RE = re.compile(r"^r/([A-Za-z0-9_]+)\s*$", flags=re.IGNORECASE)
POSTED_BY_RE = re.compile(
    r"^Posted\s+by\s+u/([A-Za-z0-9_\-]+)", flags=re.IGNORECASE
)
PERMALINK_RE = re.compile(
    r"https?://(?:www\.|old\.)?reddit\.com/r/[A-Za-z0-9_]+/comments/([a-z0-9]+)/?\S*",
    flags=re.IGNORECASE,
)
HEADER_NOISE_RE = re.compile(
    r"^(share|save|hide|report|crosspost|join|comment|reply|award|"
    r"\d+\s+(comments?|shares?|awards?)|\d+(\.\d+)?[kKmM]?\s+(upvotes?|points?)|"
    r"vote|sort by:.*|view all comments)$",
    flags=re.IGNORECASE,
)


def parse_reddit(raw_text: str) -> ParsedPost:
    if raw_text is None:
        return ParsedPost(source="reddit", content_raw="")

    text = raw_text.strip()
    if not text:
        return ParsedPost(source="reddit", content_raw="")

    # 1. JSON shape (PRAW dict, .json endpoint, etc.)
    parsed = _try_parse_json(text)
    if parsed is not None:
        return parsed

    # 2. Web copy-paste
    return _parse_web_paste(text)


def _try_parse_json(text: str) -> Optional[ParsedPost]:
    if not (text.startswith("{") or text.startswith("[")):
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    # The .json listing endpoint returns [{"data": {"children": [...]}}, ...]
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict) and "data" in first:
            children = first["data"].get("children", [])
            if children and isinstance(children[0], dict):
                inner = children[0].get("data", {})
                return _from_reddit_dict(inner)
        return None

    if isinstance(data, dict):
        # PRAW-style dump or the post object from the .json endpoint.
        if "data" in data and isinstance(data["data"], dict):
            return _from_reddit_dict(data["data"])
        return _from_reddit_dict(data)

    return None


def _from_reddit_dict(d: dict) -> ParsedPost:
    title = (d.get("title") or "").strip()
    body = (d.get("selftext") or d.get("body") or "").strip()
    content_raw = f"{title}\n\n{body}".strip() if body else title

    permalink = d.get("permalink") or ""
    if permalink and not permalink.startswith("http"):
        permalink = f"https://reddit.com{permalink}"
    url = d.get("url") or permalink

    created_utc = d.get("created_utc")
    original_date = None
    if isinstance(created_utc, (int, float)):
        original_date = datetime.fromtimestamp(
            created_utc, tz=timezone.utc
        ).isoformat()

    return ParsedPost(
        source="reddit",
        content_raw=content_raw,
        source_id=str(d.get("id") or d.get("name") or "").strip(),
        author=str(d.get("author") or "").strip(),
        url=url,
        score=int(d.get("score") or d.get("ups") or 0),
        original_date=original_date,
        extra={
            "subreddit": d.get("subreddit") or "",
            "num_comments": int(d.get("num_comments") or 0),
            "flair": d.get("link_flair_text") or "",
            "input_format": "json",
        },
    )


def _parse_web_paste(text: str) -> ParsedPost:
    lines = [ln.rstrip() for ln in text.splitlines()]

    subreddit = ""
    author = ""
    url = ""
    source_id = ""
    title_idx: Optional[int] = None
    body_lines: list[str] = []

    # First pass: pull header metadata + locate the title.
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        m_sub = SUBREDDIT_RE.match(stripped)
        if m_sub and not subreddit:
            subreddit = m_sub.group(1)
            continue

        m_author = POSTED_BY_RE.match(stripped)
        if m_author and not author:
            author = m_author.group(1)
            continue

        m_link = PERMALINK_RE.search(stripped)
        if m_link and not source_id:
            source_id = m_link.group(1)
            url = m_link.group(0)
            continue

        if HEADER_NOISE_RE.match(stripped):
            continue

        if title_idx is None:
            title_idx = i
        else:
            body_lines.append(stripped)

    if title_idx is None:
        # No title detected — whole input is the body.
        return ParsedPost(
            source="reddit",
            content_raw=text.strip(),
            author=author,
            url=url,
            source_id=source_id,
            extra={
                "subreddit": subreddit,
                "input_format": "plain",
            },
        )

    title = lines[title_idx].strip()
    body = "\n".join(line for line in body_lines if line).strip()
    content_raw = f"{title}\n\n{body}" if body else title

    return ParsedPost(
        source="reddit",
        content_raw=content_raw,
        author=author,
        url=url,
        source_id=source_id,
        extra={
            "subreddit": subreddit,
            "input_format": "web_paste",
            "title": title,
        },
    )
