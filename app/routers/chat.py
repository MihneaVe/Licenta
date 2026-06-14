"""City Assistant chat endpoint - SOTA RAG pipeline, streaming NDJSON.

POST /api/chat/
Body: {"question": str, "history": [...], "filters": {"district": str|null, "since": str|null}}
Streams application/x-ndjson events (status / meta / token / citations / done / error).
"""

import json
import logging

import requests
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ..auth import require_auth
from ..config import OLLAMA_HOST, CHAT_MODEL
from ..rag.pipeline import run_pipeline

logger = logging.getLogger(__name__)
router = APIRouter()

FRIENDLY = {
    "ollama_unavailable": "The City Assistant model isn't reachable. Make sure Ollama is running (`ollama serve`).",
    "model_missing": f"The model '{CHAT_MODEL}' isn't installed. Pull it with `ollama pull {CHAT_MODEL}`.",
    "request_failed": "Something went wrong while talking to the assistant.",
    "bad_status": "The assistant returned an unexpected response.",
}


def _probe_ollama() -> str | None:
    try:
        r = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={"model": CHAT_MODEL, "prompt": "hi", "stream": False, "options": {"num_predict": 1}},
            timeout=20,
        )
    except requests.exceptions.ConnectionError:
        return "ollama_unavailable"
    except requests.exceptions.RequestException:
        return "request_failed"
    if r.status_code == 404:
        return "model_missing"
    if r.status_code != 200:
        return "bad_status"
    return None


@router.post("/api/chat/", dependencies=[Depends(require_auth)])
async def chat(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    question = (data.get("question") or "").strip()
    history = data.get("history") if isinstance(data.get("history"), list) else []
    filters = data.get("filters") if isinstance(data.get("filters"), dict) else {}

    if not question:
        return JSONResponse({"error": "empty_question"}, status_code=400)

    err = _probe_ollama()
    if err:
        return JSONResponse(
            {"error": err, "answer": FRIENDLY.get(err, "The assistant is unavailable."), "model": CHAT_MODEL},
            status_code=503,
        )

    def event_stream():
        try:
            yield from run_pipeline(question, filters, history)
        except Exception:
            logger.exception("Unexpected error in RAG pipeline")
            yield json.dumps({"type": "error", "code": "pipeline_error",
                              "message": "An unexpected error occurred in the RAG pipeline."}) + "\n"

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
