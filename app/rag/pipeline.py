"""SOTA RAG pipeline orchestrator (yields NDJSON event strings).

Stages: query rewrite → HyDE → embed (query+HyDE averaged) → hybrid search
(dense pgvector + sparse FTS, RRF) → cross-encoder rerank → Self-RAG context
grade (re-retrieve once if < 3/5) → stream answer (qwen2.5:14b) → Corrective-RAG
answer grade.

Event protocol (one JSON object per line):
  {"type":"status","text":"…"}
  {"type":"meta","used_posts":N,"model":"…","context_score":N,"retrieval_rounds":N}
  {"type":"token","text":"…"}
  {"type":"citations","post_ids":[…],"context_score":N,"answer_score":N}
  {"type":"done"}
  {"type":"error","code":"…","message":"…"}
"""

import json
import logging
import re

import requests

from ..config import OLLAMA_HOST, CHAT_MODEL
from .embedder import embed_document, embed_query, average_embeddings
from .retriever import hybrid_search
from .reranker import rerank
from .query_expander import rewrite_query, generate_hyde

logger = logging.getLogger(__name__)

MAX_CONTEXT_POSTS = 25       # posts fed to the LLM (raised for aggregate questions)
MAX_POST_CHARS = 400
MAX_HISTORY_TURNS = 4
CONTEXT_RETRY_THRESHOLD = 3

SYSTEM_PROMPT = (
    "You are the City Assistant for UrbanPulse, a civic-sentiment dashboard for Bucharest. "
    "Answer the user's question using ONLY the numbered citizen feedback posts provided below. "
    "Cite specific posts using their number in square brackets, e.g. [3] or [1, 5]. "
    "Summarise the main pattern, give 1-3 concrete examples with citations, and name "
    "relevant locations, topics, and sentiments. "
    "If the posts don't contain enough information, say so clearly instead of inventing facts. "
    "Be concise - a short paragraph or a few bullet points is ideal."
)


# Sentiment-intent cues: when a question explicitly asks for positive or negative
# feedback, we filter retrieval to that sentiment so off-sentiment posts (e.g. a
# tree-felling complaint under "what positive things…") don't leak into the context.
_POS_CUES = ("positive", "good thing", "good news", "great", "best ", "love", "happy",
             "praise", "satisfied", "satisfaction", "improv", "nice", "excellent",
             "pleased", "wonderful", "appreciat", "success", "what's good", "whats good")
_NEG_CUES = ("negative", "worst", "hate", "upset", "angry", "anger", "complain",
             "complaint", "problem", "issue", "concern", "frustrat", "unhappy",
             "dissatisf", "broken", "dirty", "unsafe", "terrible", "awful", "annoy",
             "danger", "fail", "bad ", "worse", "outrage", "wrong")


def detect_sentiment_intent(question: str) -> str | None:
    """Return 'Positive'/'Negative' if the question clearly asks for that sentiment."""
    t = (question or "").lower()
    pos = any(c in t for c in _POS_CUES)
    neg = any(c in t for c in _NEG_CUES)
    if pos and not neg:
        return "Positive"
    if neg and not pos:
        return "Negative"
    return None


# Romanian/diacritic-aware word-char class for location boundary matching.
_WORD = "0-9a-zăâîșț"


def detect_location_intent(question: str) -> str | None:
    """Return a known district/location named in the question, else None.

    Candidates (districts + free-text location names) are matched longest-first
    so 'Calea Victoriei' wins over 'Victoriei', with word boundaries so short
    names don't match inside other words.
    """
    from .retriever import known_locations

    t = (question or "").lower()
    for low, canon in known_locations():
        if low in t and re.search(rf"(?<![{_WORD}]){re.escape(low)}(?![{_WORD}])", t):
            return canon
    return None


def _evt(type_: str, **kwargs) -> str:
    return json.dumps({"type": type_, **kwargs}) + "\n"


def _format_posts_for_prompt(posts: list[dict]) -> str:
    lines = []
    for i, p in enumerate(posts[:MAX_CONTEXT_POSTS], 1):
        content = (p.get("content") or "").replace("\n", " ").strip()[:MAX_POST_CHARS]
        loc = (p.get("location") or "-").strip() or "-"
        topic = (p.get("topic") or "-").strip() or "-"
        sent = (p.get("sentiment_label") or "-").strip() or "-"
        lines.append(f"[{i}] [{loc} | {topic} | {sent}] {content}")
    return "\n".join(lines)


def _format_history(history: list[dict]) -> str:
    turns = [h for h in (history or []) if isinstance(h, dict)][-MAX_HISTORY_TURNS * 2:]
    out = []
    for h in turns:
        textval = (h.get("content") or "").strip()[:500]
        if not textval:
            continue
        who = "User" if h.get("role") == "user" else "Assistant"
        out.append(f"{who}: {textval}")
    return "\n".join(out)


def _build_prompt(question: str, posts: list[dict], history: list[dict]) -> str:
    context = _format_posts_for_prompt(posts) or "(no relevant posts found)"
    parts = [SYSTEM_PROMPT, "", "Citizen feedback posts:", context, ""]
    hist = _format_history(history)
    if hist:
        parts += ["Conversation so far:", hist, ""]
    parts += [f"User question: {question}", "Answer:"]
    return "\n".join(parts)


def _grade(prompt_text: str, default: int = 3) -> int:
    try:
        resp = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={"model": CHAT_MODEL, "prompt": prompt_text, "stream": False,
                  "options": {"temperature": 0.0, "num_predict": 5}},
            timeout=60,
        )
        resp.raise_for_status()
        textval = (resp.json().get("response") or "").strip()
        first = next((c for c in textval if c.isdigit()), None)
        return int(first) if first else default
    except Exception:
        logger.exception("Grading call failed")
        return default


def grade_context(question: str, posts: list[dict]) -> int:
    if not posts:
        return 1
    preview = "\n".join(
        f"- [{p.get('location', '?')} | {p.get('topic', '?')}] {(p.get('content') or '')[:200]}"
        for p in posts[:6]
    )
    prompt = (
        "Rate the relevance of these retrieved posts to the question.\n"
        f"Question: {question}\nPosts:\n{preview}\n\n"
        "1 = completely irrelevant, 5 = highly relevant. Reply with a single digit 1-5, nothing else."
    )
    return _grade(prompt)


def grade_answer(question: str, posts: list[dict], answer: str) -> int:
    # Sample widely (not just the top few) so the grounding score reflects the
    # whole context the answer could draw on, not an unrepresentative slice.
    preview = "\n".join(f"- {(p.get('content') or '')[:150]}" for p in posts[:12])
    prompt = (
        "Rate how well the answer is grounded in the provided posts.\n"
        f"Question: {question}\nPosts:\n{preview}\nAnswer: {answer[:500]}\n\n"
        "1 = fabricated/not grounded, 5 = fully grounded. Reply with a single digit 1-5, nothing else."
    )
    return _grade(prompt)


def _retrieve_and_rerank(query: str, filters: dict) -> list[dict]:
    q_vec = embed_query(query)
    hyde_doc = generate_hyde(query)
    hyde_vec = embed_document(hyde_doc) if hyde_doc else None
    combined = average_embeddings([v for v in [q_vec, hyde_vec] if v]) if q_vec else None
    candidates = hybrid_search(query, combined, filters, limit=50)
    return rerank(query, candidates, top_k=MAX_CONTEXT_POSTS + 5)


def run_pipeline(question: str, filters: dict, history: list[dict]):
    # If the question explicitly asks for positive/negative feedback, constrain
    # retrieval to that sentiment so the grounding posts match the intent.
    filters = dict(filters or {})
    if "sentiment" not in filters:
        intent = detect_sentiment_intent(question)
        if intent:
            filters["sentiment"] = intent
            yield _evt("status", text=f"Focusing on {intent.lower()} feedback…")

    # If the question names a district/place (and the dashboard isn't already
    # filtering by one or more quarters), constrain retrieval to that location.
    if not filters.get("district") and not filters.get("districts") and not filters.get("location"):
        place = detect_location_intent(question)
        if place:
            filters["location"] = place
            yield _evt("status", text=f"Focusing on {place}…")

    yield _evt("status", text="Rewriting query for better retrieval…")
    rewritten = rewrite_query(question, history)
    logger.info("Query rewritten: %r → %r (sentiment=%s)", question, rewritten, filters.get("sentiment"))

    yield _evt("status", text="Searching citizen posts (hybrid dense + keyword)…")
    reranked = _retrieve_and_rerank(rewritten, filters)

    yield _evt("status", text="Grading context relevance…")
    context_score = grade_context(question, reranked)
    retrieval_rounds = 1

    if context_score < CONTEXT_RETRY_THRESHOLD:
        yield _evt("status", text="Context weak - re-retrieving with a refined query…")
        retry_q = rewrite_query(
            f"{question} [need more specific and relevant results than the previous search]",
            history,
        )
        reranked2 = _retrieve_and_rerank(retry_q, filters)
        if reranked2:
            score2 = grade_context(question, reranked2)
            if score2 >= context_score:
                reranked, context_score = reranked2, score2
        retrieval_rounds = 2

    context_posts = reranked[:MAX_CONTEXT_POSTS]

    # Compact post objects for the frontend "See posts" modal - the actual
    # quotes the answer is grounded on (numbered to match any [n] citations).
    cited = [
        {
            "n": i,
            "id": p["id"],
            "content": (p.get("content") or "").strip(),
            "location": p.get("location") or "",
            "topic": p.get("topic") or "",
            "sentiment_label": p.get("sentiment_label") or "",
            "url": p.get("url") or "",
        }
        for i, p in enumerate(context_posts, 1)
    ]
    yield _evt("meta", used_posts=len(context_posts), model=CHAT_MODEL,
               context_score=context_score, retrieval_rounds=retrieval_rounds,
               posts=cited)

    prompt = _build_prompt(question, context_posts, history)

    try:
        upstream = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={"model": CHAT_MODEL, "prompt": prompt, "stream": True,
                  "options": {"temperature": 0.3, "num_predict": 800}},
            stream=True, timeout=300,
        )
    except requests.exceptions.ConnectionError:
        yield _evt("error", code="ollama_unavailable",
                   message="Ollama is unreachable. Make sure `ollama serve` is running.")
        return
    except requests.exceptions.RequestException:
        logger.exception("Ollama connect failed")
        yield _evt("error", code="request_failed", message="Failed to connect to the assistant model.")
        return

    if upstream.status_code == 404:
        upstream.close()
        yield _evt("error", code="model_missing",
                   message=f"Model '{CHAT_MODEL}' not found. Run `ollama pull {CHAT_MODEL}`.")
        return
    if upstream.status_code != 200:
        upstream.close()
        yield _evt("error", code="bad_status",
                   message=f"Unexpected Ollama response: HTTP {upstream.status_code}.")
        return

    answer_tokens: list[str] = []
    buffer = b""
    try:
        for chunk in upstream.raw.stream(decode_content=True):
            if not chunk:
                continue
            buffer += chunk
            while b"\n" in buffer:
                raw_line, buffer = buffer.split(b"\n", 1)
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    continue
                token = obj.get("response", "")
                if token:
                    answer_tokens.append(token)
                    yield _evt("token", text=token)
                if obj.get("done"):
                    break
    except Exception:
        logger.exception("Ollama stream interrupted")
        yield _evt("error", code="stream_interrupted",
                   message="The connection to the model was interrupted.")
        return
    finally:
        upstream.close()

    full_answer = "".join(answer_tokens)
    answer_score = grade_answer(question, context_posts, full_answer)
    logger.info("Answer grounding score: %d / 5", answer_score)

    yield _evt("citations", post_ids=[p["id"] for p in context_posts],
               context_score=context_score, answer_score=answer_score)
    yield _evt("done")
