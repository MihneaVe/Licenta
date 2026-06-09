"""Text normalization for ingested social-media content.

Produces the cleaned string that gets handed to the NLP pipeline
(``interpreters.mood_analyzer.MoodAnalyzer``). Romanian-aware: preserves
diacritics and folds the legacy cedilla codepoints (ş/ţ) into the modern
comma-below ones (ș/ț) that the downstream HuggingFace tokenizer expects.
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass


URL_RE = re.compile(r"https?://\S+|www\.\S+", flags=re.IGNORECASE)
EMAIL_RE = re.compile(r"\S+@\S+\.\S+")
HTML_TAG_RE = re.compile(r"<[^>]+>")
MENTION_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{1,50}")
HASHTAG_RE = re.compile(r"(?<!\w)#(\w+)", flags=re.UNICODE)
WHITESPACE_RE = re.compile(r"\s+")
RT_PREFIX_RE = re.compile(r"^RT @\w+:\s*", flags=re.IGNORECASE)

# Zero-width / bidi / formatting controls — defined via escape sequences
# so the source file stays free of invisible bytes.
ZERO_WIDTH_RE = re.compile(
    "["
    "​-‏"  # ZWSP, ZWNJ, ZWJ, LRM, RLM
    "‪-‮"  # bidi embedding/override
    "⁠-⁤"  # word joiner, invisible operators
    "﻿"         # BOM / ZWNBSP
    "]"
)

# Reddit/X reaction noise that appears when copy-pasting from the web UI.
REDDIT_VOTE_RE = re.compile(
    r"^\s*\d+(\.\d+)?[kKmM]?\s*(upvotes?|points?|comments?|shares?|awards?)\s*$",
    flags=re.IGNORECASE,
)
X_METRIC_RE = re.compile(
    r"^\s*\d+(\.\d+)?[kKmM]?\s*(replies?|reposts?|likes?|views?|bookmarks?)\s*$",
    flags=re.IGNORECASE,
)

# ş/Ş (cedilla, U+015F/U+015E) → ș/Ș (comma-below, U+0219/U+0218)
# ţ/Ţ (cedilla, U+0163/U+0162) → ț/Ț (comma-below, U+021B/U+021A)
DIACRITIC_FOLD = {
    "ş": "ș",
    "Ş": "Ș",
    "ţ": "ț",
    "Ţ": "Ț",
}


@dataclass
class NormalizedText:
    """Result of normalization — what the NLP pipeline consumes."""

    clean: str
    char_count: int
    word_count: int
    removed_urls: int
    removed_mentions: int
    removed_hashtags: int
    is_empty: bool


def _fold_diacritics(text: str) -> str:
    for old, new in DIACRITIC_FOLD.items():
        text = text.replace(old, new)
    return text


def _strip_emoji(text: str) -> str:
    """Drop pictographic codepoints. Keep letters and punctuation."""
    out = []
    for ch in text:
        cat = unicodedata.category(ch)
        if cat in ("So", "Cs", "Cn"):
            continue
        out.append(ch)
    return "".join(out)


def normalize(
    raw: str,
    *,
    drop_emoji: bool = True,
    keep_hashtag_word: bool = True,
) -> NormalizedText:
    """Clean a raw social-media string into something NLP-ready.

    Args:
        raw: Input text exactly as pasted by the user.
        drop_emoji: Strip emoji glyphs. The Romanian XLM-R sentiment
            checkpoint scores more reliably without them.
        keep_hashtag_word: For "#trafic" → keep the word "trafic" so the
            zero-shot topic classifier still sees the term. False drops
            the whole hashtag.
    """
    if raw is None:
        return NormalizedText("", 0, 0, 0, 0, 0, True)

    text = html.unescape(raw)
    text = unicodedata.normalize("NFC", text)
    text = ZERO_WIDTH_RE.sub("", text)
    text = _fold_diacritics(text)

    text = HTML_TAG_RE.sub(" ", text)

    removed_urls = len(URL_RE.findall(text))
    text = URL_RE.sub(" ", text)
    text = EMAIL_RE.sub(" ", text)

    text = RT_PREFIX_RE.sub("", text)

    removed_mentions = len(MENTION_RE.findall(text))
    text = MENTION_RE.sub(" ", text)

    hashtag_matches = HASHTAG_RE.findall(text)
    removed_hashtags = len(hashtag_matches)
    if keep_hashtag_word:
        text = HASHTAG_RE.sub(r"\1", text)
    else:
        text = HASHTAG_RE.sub(" ", text)

    if drop_emoji:
        text = _strip_emoji(text)

    kept_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if REDDIT_VOTE_RE.match(stripped) or X_METRIC_RE.match(stripped):
            continue
        kept_lines.append(stripped)
    text = " ".join(kept_lines)

    text = WHITESPACE_RE.sub(" ", text).strip()

    words = text.split() if text else []
    return NormalizedText(
        clean=text,
        char_count=len(text),
        word_count=len(words),
        removed_urls=removed_urls,
        removed_mentions=removed_mentions,
        removed_hashtags=removed_hashtags,
        is_empty=not text,
    )
