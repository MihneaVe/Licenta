"""Unit tests for the Reddit / X paste parsers — pure parsing, no DB."""

import json

import pytest

from app.ingestion.parsers import ParserError, parse
from app.ingestion.parsers.reddit import parse_reddit
from app.ingestion.parsers.x import parse_x


# --- dispatch ---------------------------------------------------------------

def test_dispatch_unknown_source_raises():
    with pytest.raises(ParserError):
        parse("facebook", "ceva")


def test_dispatch_twitter_alias_maps_to_x():
    assert parse("twitter", "un tweet").source == "x"


# --- reddit -----------------------------------------------------------------

def test_reddit_web_paste_extracts_metadata():
    raw = "\n".join([
        "r/bucuresti",
        "Posted by u/cetatean_suparat • 5h",
        "245 upvotes",
        "Gropile de pe Calea Victoriei",
        "Am rupt o roata azi dimineata. Primaria nu raspunde.",
        "53 comments",
        "share",
        "https://reddit.com/r/bucuresti/comments/abc123/gropile/",
    ])
    p = parse_reddit(raw)
    assert p.source == "reddit"
    assert p.author == "cetatean_suparat"
    assert p.source_id == "abc123"
    assert p.extra["subreddit"] == "bucuresti"
    assert p.content_raw.startswith("Gropile de pe Calea Victoriei")
    assert "Am rupt o roata" in p.content_raw
    assert "53 comments" not in p.content_raw
    assert "share" not in p.content_raw.split("\n")


def test_reddit_json_paste():
    raw = json.dumps({
        "id": "xyz789",
        "title": "Trafic infernal in Berceni",
        "selftext": "Dimineata e blocat tot.",
        "author": "user_unu",
        "score": 87,
        "permalink": "/r/bucuresti/comments/xyz789/trafic/",
        "created_utc": 1718000000,
        "subreddit": "bucuresti",
        "num_comments": 12,
    })
    p = parse_reddit(raw)
    assert p.source_id == "xyz789"
    assert p.author == "user_unu"
    assert p.score == 87
    assert p.content_raw == "Trafic infernal in Berceni\n\nDimineata e blocat tot."
    assert p.url.startswith("https://reddit.com/r/bucuresti")
    assert p.original_date is not None
    assert p.extra["input_format"] == "json"


def test_reddit_plain_text_becomes_content():
    p = parse_reddit("Doar o observatie despre parcul din cartier.")
    assert p.content_raw == "Doar o observatie despre parcul din cartier."
    assert p.author == ""


# --- x ----------------------------------------------------------------------

def test_x_web_paste_anchors_on_handle():
    raw = "\n".join([
        "Ion Popescu",
        "@ion_popescu",
        "5h",
        "STB a anulat iar linia 312. A treia oara saptamana asta.",
        "12 Replies 34 Reposts 156 Likes",
    ])
    p = parse_x(raw)
    assert p.source == "x"
    assert p.author == "ion_popescu"
    assert p.content_raw == "STB a anulat iar linia 312. A treia oara saptamana asta."
    assert "Ion Popescu" not in p.content_raw  # display name dropped
    assert "Likes" not in p.content_raw        # metrics stripped


def test_x_status_url_provides_id_and_author():
    raw = "\n".join([
        "Mizerie in Cismigiu, nimeni nu strange.",
        "https://x.com/civic_buc/status/1801234567890123456",
    ])
    p = parse_x(raw)
    assert p.source_id == "1801234567890123456"
    assert p.author == "civic_buc"
    assert p.url.startswith("https://x.com/")
    assert "Mizerie in Cismigiu" in p.content_raw
    assert "status" not in p.content_raw


def test_x_plain_text_inline_handle():
    p = parse_x("Felicitari @primaria6 pentru noul parc!")
    assert p.author == "primaria6"
    assert p.content_raw == "Felicitari @primaria6 pentru noul parc!"
    assert p.extra["input_format"] == "plain"
