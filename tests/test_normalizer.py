"""Unit tests for app.ingestion.normalizer — pure text cleaning, no DB."""

from app.ingestion.normalizer import normalize


def test_empty_and_none_input():
    assert normalize(None).is_empty
    assert normalize("").is_empty
    assert normalize("   \n  ").is_empty


def test_urls_removed_and_counted():
    r = normalize("Gropi pe strada https://example.com/a si www.foo.ro aici")
    assert r.removed_urls == 2
    assert "http" not in r.clean and "www" not in r.clean
    assert "Gropi pe strada" in r.clean


def test_mentions_removed_hashtag_word_kept():
    r = normalize("@primarie nu face nimic #trafic in centru")
    assert r.removed_mentions == 1
    assert r.removed_hashtags == 1
    assert "@primarie" not in r.clean
    assert "trafic" in r.clean  # hashtag word survives for the topic classifier
    assert "#" not in r.clean


def test_legacy_cedilla_diacritics_folded():
    # ş (U+015F) / ţ (U+0163) → ș (U+0219) / ț (U+021B)
    r = normalize("Aceastş straţie")
    assert "ș" in r.clean and "ț" in r.clean
    assert "ş" not in r.clean and "ţ" not in r.clean


def test_vote_and_metric_lines_dropped():
    raw = "Titlu important\n245 upvotes\n12 comments\nCorpul postarii\n3.1K Views"
    r = normalize(raw)
    assert "upvotes" not in r.clean.lower()
    assert "views" not in r.clean.lower()
    assert "Titlu important" in r.clean and "Corpul postarii" in r.clean


def test_html_unescaped_and_tags_stripped():
    r = normalize("Mai mult &amp; mai <b>bine</b>")
    assert r.clean == "Mai mult & mai bine"


def test_counts_match_clean_text():
    r = normalize("unu doi trei")
    assert r.word_count == 3
    assert r.char_count == len("unu doi trei")
