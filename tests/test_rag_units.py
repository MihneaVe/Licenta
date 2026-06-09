"""Unit tests for pure RAG pipeline helpers — no DB, no Ollama.

detect_location_intent's district list is monkeypatched; everything else
under test is a pure function.
"""

import app.rag.retriever as retriever
from app.rag.pipeline import detect_location_intent, detect_sentiment_intent
from app.rag.retriever import rrf_fusion


# --- sentiment intent --------------------------------------------------------

def test_positive_intent():
    assert detect_sentiment_intent("What positive things are people saying?") == "Positive"


def test_negative_intent():
    assert detect_sentiment_intent("What are the main complaints about garbage?") == "Negative"


def test_no_intent_on_neutral_question():
    assert detect_sentiment_intent("What is happening in Rahova?") is None


def test_mixed_cues_yield_no_intent():
    assert detect_sentiment_intent("List the best and worst things about the metro") is None


# --- location intent ---------------------------------------------------------

def _fake_locations():
    # (lowercase, canonical), longest-first — the contract of known_locations().
    return [
        ("calea victoriei", "Calea Victoriei"),
        ("tei toboc", "Tei Toboc"),
        ("victoriei", "Victoriei"),
        ("tei", "Tei"),
    ]


def test_longest_location_wins(monkeypatch):
    monkeypatch.setattr(retriever, "known_locations", _fake_locations)
    assert detect_location_intent("traffic on calea victoriei today") == "Calea Victoriei"


def test_location_word_boundary(monkeypatch):
    monkeypatch.setattr(retriever, "known_locations", _fake_locations)
    # 'tei' must not match inside 'teiul'
    assert detect_location_intent("pe strada teiul doamnei") is None
    assert detect_location_intent("ce se intampla in tei?") == "Tei"


def test_no_location(monkeypatch):
    monkeypatch.setattr(retriever, "known_locations", _fake_locations)
    assert detect_location_intent("how clean is the city?") is None


# --- RRF fusion ---------------------------------------------------------------

def _doc(i):
    return {"id": i, "content": f"post {i}"}


def test_rrf_doc_in_both_lists_outranks_single_list_docs():
    dense = [_doc(1), _doc(2), _doc(3)]
    sparse = [_doc(2), _doc(4)]
    fused = rrf_fusion(dense, sparse, k=60, limit=10)
    assert fused[0]["id"] == 2  # appears in both rankings
    ids = [d["id"] for d in fused]
    assert sorted(ids) == [1, 2, 3, 4]  # deduplicated union


def test_rrf_scores_attached_and_monotonic():
    fused = rrf_fusion([_doc(1), _doc(2)], [_doc(3)], limit=10)
    scores = [d["rrf_score"] for d in fused]
    assert all(isinstance(s, float) for s in scores)
    assert scores == sorted(scores, reverse=True)


def test_rrf_respects_limit():
    dense = [_doc(i) for i in range(20)]
    assert len(rrf_fusion(dense, [], limit=5)) == 5
