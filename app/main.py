"""UrbanPulse FastAPI application entry point.

Run locally:
    uvicorn app.main:app --reload --port 8000

Exposes the endpoints consumed by the React dashboard:
    POST /api/chat/           - streaming NDJSON RAG answer
    POST /api/rag/feedback/   - thumbs up/down
    POST /api/ingest/         - manual paste ingestion (Add Post)
    GET  /healthz             - liveness probe
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import AUTH_ENABLED, CORS_ORIGINS
from .routers import chat, feedback, ingest

logging.basicConfig(level=logging.INFO)
logging.getLogger(__name__).info(
    "Auth0 JWT protection on write/compute endpoints: %s",
    "ON" if AUTH_ENABLED else "OFF (set AUTH0_DOMAIN + AUTH0_AUDIENCE to enable)",
)

app = FastAPI(title="UrbanPulse API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, tags=["chat"])
app.include_router(feedback.router, tags=["feedback"])
app.include_router(ingest.router, tags=["ingest"])


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "urbanpulse-api"}
