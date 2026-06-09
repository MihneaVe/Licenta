# CivicPulse — Bucharest Civic Sentiment Tracker

Bachelor's thesis project. Collects civic posts about Bucharest (manual
Reddit/X paste + an LLM-driven synthetic generator), runs them through a local
NLP pipeline (sentiment + zero-shot topics + NER + quarter assignment), embeds
them with pgvector, and serves a React dashboard with a RAG-powered **City
Assistant** that answers questions grounded in citizen feedback — everything
keyed off the city's ~80 traditional quarters (cartiere) plus its six sectors.

All models run locally: HuggingFace for NLP, Ollama for the LLM and embeddings.
No paid APIs.

## Architecture

```
                          ┌──────────────────────────┐
                          │    Supabase Postgres     │
                          │      (pgvector)          │
                          │                          │
                          │  analytics_* / rag_*     │ ←── FastAPI + scripts (owner)
                          │  feedbacks, quarters_map │ ←── React reads (anon, SELECT-only)
                          │  + 2 more SQL views      │
                          └────────────▲─────────────┘
                                       │
              ┌────────────────────────┴────────────────────────┐
              │                                                 │
     ┌────────▼─────────┐                              ┌────────▼────────┐
     │  FastAPI  :8000  │ ◀── /api/chat/ (NDJSON) ──── │   React :5173   │
     │                  │ ◀── /api/ingest/  ────────── │  (UrbanPulse)   │
     │  RAG pipeline    │ ◀── /api/rag/feedback/ ───── │                 │
     │  rewrite → HyDE  │                              │  /dashboard     │
     │  → hybrid search │                              │  /heatmap (Leaflet)
     │  → rerank → LLM  │                              │  /topics /live-feed
     └────────┬─────────┘                              │  /assistant     │
              │                                        │  Auth0 login    │
     ┌────────▼─────────┐                              └─────────────────┘
     │  Ollama (host)   │
     │  qwen2.5:14b     │  generation, rewriting, HyDE, grading
     │  nomic-embed-text│  768-dim embeddings
     └──────────────────┘
```

The FastAPI side owns ingestion and the RAG assistant; batch scripts own the
heavy data work (NLP, embeddings, scoring). The React side reads Supabase
views directly and calls the API for chat/ingest. Schema is migrated with
Alembic — including the SQL views and the row-level-security setup.

## Modules at a glance

```
.
├── app/                        FastAPI application
│   ├── main.py                 entry point (uvicorn app.main:app)
│   ├── config.py  db.py        env config, SQLAlchemy engine/session
│   ├── models.py               SQLAlchemy models (analytics_* + rag_*)
│   ├── ingestion/              paste → parser → normalizer → DB
│   │   └── parsers/            Reddit & X paste parsers
│   ├── rag/                    pipeline, retriever (hybrid+RRF), embedder,
│   │                           reranker (bge-reranker-v2-m3), query expander
│   └── routers/                /api/chat/, /api/rag/feedback/, /api/ingest/
├── scripts/                    batch entry points (python -m scripts.<name>)
│   ├── ingest.py               manual paste from file/stdin
│   ├── process_posts.py        sentiment + topics + language + district
│   ├── embed_posts.py          nomic-embed-text → rag_postembedding
│   ├── compute_scores.py       per-district scores → analytics_districtscore
│   ├── pipeline.py             process → embed → score, chained
│   ├── eval_rag.py             retrieval evaluation with ablations
│   ├── generate_synthetic.py   agentic synthetic post generator (Ollama)
│   └── insert_synthetic.py     JSONL → Supabase bulk insert
├── interpreters/               HF sentiment (XLM-R), zero-shot topics
│                               (mDeBERTa), spaCy NER
├── synthetic/                  generator engine + Bucharest taxonomy/streets
├── geo/                        Overpass + Nominatim helpers (quarter seeds)
├── scrapers/                   legacy scrapers (Reddit/Maps/FB) — optional
├── alembic/                    migrations: 0001 schema, 0002 views + RLS
├── eval/                       golden_set.json (+ gitignored results/)
├── tests/                      pytest unit suite (no DB / no Ollama needed)
├── frontend-react/             React 19 + Vite + Tailwind dashboard
└── designs/                    original HTML mockups
```

## Quickstart (Docker)

```bash
# 1. Fill in DB credentials (Supabase pooler or local Postgres)
vi .env

# 2. Ollama on the host with the two models pulled
ollama pull qwen2.5:14b
ollama pull nomic-embed-text
ollama serve

# 3. Build + run web + frontend
docker compose up --build
# → FastAPI  http://localhost:8000/docs
# → React    http://localhost:5173/
```

Optional local Postgres instead of Supabase (`pgvector/pgvector:pg16`):

```bash
docker compose --profile localdb up postgres web
# then: alembic upgrade head   (creates tables, views, and grants)
```

## Without Docker (host Python + Node)

```powershell
# Backend ----------------------------------
py -m pip install -r requirements.txt
py -m spacy download ro_core_news_sm     # Romanian NER (optional but better)
py -m uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal) -------------
cd frontend-react
npm install
npm run dev                              # → http://localhost:5173/
```

## Required env vars (`.env`)

```env
# Supabase / Postgres
DB_HOST=aws-1-eu-west-1.pooler.supabase.com
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres.<your-project-ref>
DB_PASSWORD=<your-db-password>
# or override everything at once:
# DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/db

# Ollama (host machine; compose maps host.docker.internal for you)
OLLAMA_HOST=http://localhost:11434
OLLAMA_CHAT_MODEL=qwen2.5:14b
EMBED_MODEL=nomic-embed-text

# CORS for the SPA ("*" in dev)
CORS_ORIGINS=*
```

The React app reads `frontend-react/.env`: `VITE_SUPABASE_URL`,
`VITE_SUPABASE_ANON_KEY`, `VITE_AUTH0_*`, and `VITE_API_URL`
(the FastAPI origin, default `http://localhost:8000`).

## Data pipeline

```powershell
# Add a post: paste UI (sidebar → Add Post), or API, or CLI
py -m scripts.ingest --source reddit --file post.txt

# NLP + embeddings + district scores for everything new
py -m scripts.pipeline
# … or the individual steps:
py -m scripts.process_posts            # sentiment/topics/language/district
py -m scripts.embed_posts              # pgvector embeddings via Ollama
py -m scripts.compute_scores --days 30 # per-quarter scores + grades

# Generate synthetic civic posts (agentic draft→critique→revise loop)
py -m scripts.generate_synthetic --count 100
```

Posts added through the dashboard's **Add Post** modal (or `POST /api/ingest/`)
are processed automatically: the endpoint spawns `scripts.pipeline` in the
background, so sentiment, topic, quarter, and the embedding appear without any
manual step.

## City Assistant (RAG)

`POST /api/chat/` streams NDJSON events through this pipeline:

1. **Intent detection** — explicit positive/negative phrasing and quarter
   names in the question become retrieval filters
2. **Query rewrite** (qwen2.5:14b) — standalone search phrase
3. **HyDE** — a hypothetical post is generated and embedded alongside the query
4. **Hybrid retrieval** — dense (pgvector HNSW, cosine) + sparse (Postgres
   FTS), fused with Reciprocal Rank Fusion, re-weighted by accumulated
   thumbs up/down feedback
5. **Cross-encoder rerank** — BAAI/bge-reranker-v2-m3, local
6. **Self-RAG context grading** — weak context triggers one refined
   re-retrieval round
7. **Streamed answer** with numbered citations + a final grounding grade

## Evaluation

```powershell
py -m scripts.eval_rag --variants full,no-hyde,no-rerank,dense,sparse --judge
```

Replays `eval/golden_set.json` (24 label-tagged questions) through the
retrieval stack with stages ablated, reporting precision@k, hit@k, MRR, and an
optional LLM context grade. JSON + Markdown reports land in `eval/results/`.

## Tests

```powershell
py -m pytest tests/        # 32 unit tests, no DB or Ollama required
```

## Endpoints & pages

### FastAPI (`localhost:8000`)

| Path                  | What                                            |
|-----------------------|-------------------------------------------------|
| `POST /api/chat/`     | streaming NDJSON RAG answer                     |
| `POST /api/rag/feedback/` | thumbs up/down on an answer                 |
| `POST /api/ingest/`   | manual paste ingestion (+ background pipeline)  |
| `GET /healthz`        | liveness probe                                  |
| `GET /docs`           | OpenAPI UI                                      |

### React (`localhost:5173`)

| Path                   | What                                           |
|------------------------|------------------------------------------------|
| `/`                    | landing page (Auth0 sign-in)                   |
| `/dashboard`           | overview — KPI cards + recent feedback         |
| `/dashboard/heatmap`   | quarter polygons shaded by sentiment (Leaflet) |
| `/dashboard/topics`    | topic explorer                                 |
| `/dashboard/live-feed` | filterable feedback grid                       |
| `/dashboard/assistant` | City Assistant chat (citations, see-posts)     |
| `/dashboard/settings`  | preferences                                    |

## Data model

```
District (kind ∈ {city, sector, quarter}, boundary_geojson, centroids)
   └─ parent → District (city → sectors → quarters)

SocialPost ─ district FK, sentiment, topic_scores, language, extra_data
   ├─ topics  M2M → TopicCategory (infrastructure, cleanliness, safety,
   │                               transport, greenspace, other)
   └─ rag_postembedding (vector(768), HNSW index)

DistrictScore — per (district, period): avg sentiment, issue count,
                0-10 composite, A-F grade, topic breakdown
RagFeedback   — thumbs up/down per answer; re-weights future retrieval

SQL views (anon SELECT-only; everything else RLS-denied):
   feedbacks, feedbacks_overview, feedbacks_topics, quarters_map
```

## Stack

- **Backend**  FastAPI, SQLAlchemy 2, Alembic, Postgres (Supabase) + pgvector
- **NLP**      `cardiffnlp/twitter-xlm-roberta-base-sentiment`,
               `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` (zero-shot topics),
               spaCy `ro_core_news_sm` (NER)
- **RAG**      `nomic-embed-text` embeddings, Postgres FTS, RRF,
               `BAAI/bge-reranker-v2-m3` cross-encoder, `qwen2.5:14b`
               generation/rewrite/HyDE/grading — all local via Ollama
- **Frontend** React 19, Vite, Tailwind, react-leaflet, Auth0, supabase-js
