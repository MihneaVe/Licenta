"""RAG feedback endpoint — thumbs up/down on assistant answers.

POST /api/rag/feedback/
Body: {session_id?, question, answer, retrieved_post_ids: [int], rating: 'up'|'down',
       context_score?, answer_score?}
Stored in rag_feedback (Supabase) for offline eval + retrieval re-weighting.
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..db import SessionLocal
from ..models import RagFeedback

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/rag/feedback/")
async def feedback(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    rating = data.get("rating", "")
    if rating not in ("up", "down"):
        return JSONResponse({"error": "rating must be 'up' or 'down'"}, status_code=400)

    question = (data.get("question") or "").strip()
    if not question:
        return JSONResponse({"error": "question is required"}, status_code=400)

    answer = (data.get("answer") or "").strip()
    post_ids = data.get("retrieved_post_ids")
    if not isinstance(post_ids, list):
        post_ids = []
    clean_ids = [int(i) for i in post_ids if isinstance(i, (int, str)) and str(i).isdigit()]

    def _score(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    try:
        with SessionLocal() as s:
            fb = RagFeedback(
                session_id=(data.get("session_id") or "")[:64],
                question=question[:2000],
                answer=answer[:8000],
                retrieved_post_ids=clean_ids,
                rating=rating,
                context_score=_score(data.get("context_score")),
                answer_score=_score(data.get("answer_score")),
            )
            s.add(fb)
            s.commit()
            s.refresh(fb)
            new_id = fb.id
        logger.info("RagFeedback #%s: %s posts=%s", new_id, rating, clean_ids[:5])
        return JSONResponse({"id": new_id}, status_code=201)
    except Exception:
        logger.exception("feedback: failed to save")
        return JSONResponse({"error": "internal error"}, status_code=500)
