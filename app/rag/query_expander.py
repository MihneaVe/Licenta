"""Query expansion: rewriting + HyDE (Hypothetical Document Embeddings).

Both call qwen2.5:14b via Ollama and fall back gracefully (returning the
original text) on any network or parse error.
"""

import logging

import requests

from ..config import OLLAMA_HOST, CHAT_MODEL

logger = logging.getLogger(__name__)


def _generate(prompt: str, temperature: float = 0.2, max_tokens: int = 200) -> str:
    try:
        resp = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": CHAT_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
            timeout=90,
        )
        resp.raise_for_status()
        return (resp.json().get("response") or "").strip()
    except Exception:
        logger.exception("_generate() failed (model=%s)", CHAT_MODEL)
        return ""


def rewrite_query(question: str, history: list[dict] | None = None) -> str:
    ctx = ""
    if history:
        recent = [h for h in history if isinstance(h, dict)][-4:]
        lines = [f"{h.get('role', '?').capitalize()}: {(h.get('content') or '')[:200]}" for h in recent]
        ctx = "Conversation context:\n" + "\n".join(lines) + "\n\n"

    prompt = (
        f"{ctx}"
        f"Original question: {question}\n\n"
        "Rewrite this as a standalone natural-language search phrase for finding "
        "relevant Bucharest citizen-feedback posts (civic issues, neighborhoods, "
        "public services). Resolve pronouns and references using the conversation "
        "context. Use plain keywords and phrases a resident might write — NOT SQL, "
        "NOT code, no field names, no operators. "
        "Return ONLY the rewritten search phrase, nothing else.\n\n"
        "Example: 'transport complaints and bus delays in Sector 3'"
    )
    result = _generate(prompt, temperature=0.1, max_tokens=80)
    return result if result else question


def generate_hyde(question: str) -> str:
    prompt = (
        f"Question about Bucharest citizen feedback: {question}\n\n"
        "Write a short (2-4 sentence) hypothetical social-media post from a "
        "Bucharest resident that directly addresses this question. "
        "Mention a specific neighborhood or sector, the type of civic issue, "
        "and the resident's sentiment. Write it like a real post, not a summary. "
        "Return ONLY the post text."
    )
    return _generate(prompt, temperature=0.5, max_tokens=150)
