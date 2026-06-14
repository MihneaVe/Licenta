"""Embedding service via Ollama (nomic-embed-text, fully local, 768-dim).

nomic-embed-text supports task-type prefixes that improve retrieval quality:
  "search_document: <text>"  - corpus chunks stored in the index
  "search_query:    <text>"  - the user query at search time
"""

import logging

import requests

from ..config import OLLAMA_HOST, EMBED_MODEL

logger = logging.getLogger(__name__)

_EMBED_DIM = 768
_MAX_CHARS = 4096


def embed_text(text: str) -> list[float] | None:
    text = (text or "").strip()[:_MAX_CHARS]
    if not text:
        return None
    try:
        resp = requests.post(
            f"{OLLAMA_HOST}/api/embed",
            json={"model": EMBED_MODEL, "input": text},
            timeout=60,
        )
        if resp.status_code == 200:
            embs = resp.json().get("embeddings", [])
            if embs:
                return embs[0]
        resp = requests.post(
            f"{OLLAMA_HOST}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json().get("embedding")
    except Exception:
        logger.exception("embed_text failed (model=%s)", EMBED_MODEL)
        return None


def embed_document(text: str) -> list[float] | None:
    return embed_text(f"search_document: {text}")


def embed_query(text: str) -> list[float] | None:
    return embed_text(f"search_query: {text}")


def average_embeddings(vecs: list[list[float]]) -> list[float] | None:
    valid = [v for v in vecs if v and len(v) == _EMBED_DIM]
    if not valid:
        return None
    n = len(valid)
    return [sum(v[i] for v in valid) / n for i in range(_EMBED_DIM)]


def is_available() -> bool:
    v = embed_query("health check")
    return bool(v) and len(v) == _EMBED_DIM
