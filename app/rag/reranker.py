"""Local cross-encoder reranker using BAAI/bge-reranker-v2-m3.

Multilingual XLM-RoBERTa cross-encoder loaded via raw transformers + torch
(no sentence-transformers dependency). Lazy-loaded on first call; falls back to
the input order if torch/transformers or the model can't load.
"""

import logging

from ..config import RERANKER_MODEL

logger = logging.getLogger(__name__)

_MAX_LENGTH = 512
_pair = None  # (tokenizer, model) | False


def _get_model():
    global _pair
    if _pair is not None:
        return _pair
    try:
        import torch  # noqa: F401
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        logger.info("Loading cross-encoder reranker %r …", RERANKER_MODEL)
        tok = AutoTokenizer.from_pretrained(RERANKER_MODEL)
        model = AutoModelForSequenceClassification.from_pretrained(RERANKER_MODEL)
        model.eval()
        _pair = (tok, model)
        logger.info("Reranker ready.")
    except Exception:
        logger.exception("Reranker unavailable — falling back to fused order")
        _pair = False
    return _pair


def rerank(query: str, candidates: list[dict], top_k: int = 15) -> list[dict]:
    if not candidates:
        return candidates
    loaded = _get_model()
    if not loaded:
        return candidates[:top_k]
    try:
        import torch

        tok, model = loaded
        pairs = [[query, (c.get("content") or "")[:800]] for c in candidates]
        with torch.no_grad():
            inputs = tok(pairs, padding=True, truncation=True, return_tensors="pt", max_length=_MAX_LENGTH)
            scores = model(**inputs, return_dict=True).logits.view(-1).float().tolist()
        ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
        out = []
        for score, doc in ranked[:top_k]:
            doc = dict(doc)
            doc["rerank_score"] = float(score)
            out.append(doc)
        return out
    except Exception:
        logger.exception("rerank() failed — returning fused order")
        return candidates[:top_k]
