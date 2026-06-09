"""Manual paste ingestion endpoint — replaces the former Django /ingest/ form.

POST /api/ingest/
Body: {"source": "reddit"|"x", "text": str, "process": bool (default true)}

Persists the pasted post (idempotent on content hash), then — unless
process=false — kicks off `scripts.pipeline --skip-scores` in a detached
subprocess so the new post gains sentiment, topics, a district, and an
embedding without blocking the response or loading the NLP models into the
web process.
"""

import logging
import subprocess
import sys

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..ingestion.service import IngestionError, ingest_post

logger = logging.getLogger(__name__)
router = APIRouter()


def _schedule_processing() -> bool:
    try:
        subprocess.Popen(
            [sys.executable, "-m", "scripts.pipeline", "--skip-scores"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        logger.exception("Failed to spawn the processing pipeline")
        return False


@router.post("/api/ingest/")
async def ingest(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    source = (data.get("source") or "").strip().lower()
    raw_text = data.get("text") or ""
    process = data.get("process", True)

    if source not in ("reddit", "x"):
        return JSONResponse({"error": "source must be 'reddit' or 'x'"}, status_code=400)

    try:
        result = ingest_post(source, raw_text)
    except IngestionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception:
        logger.exception("ingest: unexpected failure")
        return JSONResponse({"error": "internal error"}, status_code=500)

    scheduled = _schedule_processing() if (process and result.created) else False
    logger.info("Ingested post #%s (%s, created=%s, processing=%s)",
                result.post_id, result.source, result.created, scheduled)
    return JSONResponse(
        {
            "id": result.post_id,
            "source": result.source,
            "created": result.created,
            "content": result.content[:500],
            "processing": "scheduled" if scheduled else "skipped",
        },
        status_code=201 if result.created else 200,
    )
