# UrbanPulse

Bucharest civic sentiment tracker. Bachelor's thesis project.

UrbanPulse collects civic posts about Bucharest, runs them through a local NLP
pipeline (sentiment, zero-shot topics, NER, quarter assignment), embeds them
with pgvector, and serves a React dashboard with a RAG assistant that answers
questions grounded in the collected feedback. Everything is keyed to the city's
traditional quarters (cartiere) and its six sectors.

Posts come from two sources: manual Reddit/X paste and a local LLM that
generates synthetic posts. All models run locally (HuggingFace for the NLP
models, Ollama for the LLM and embeddings), so there are no paid APIs.

## How it fits together

* FastAPI (port 8000) handles ingestion and the RAG assistant.
* Batch scripts do the heavy data work: NLP, embeddings, per-quarter scoring.
* The React dashboard (port 5173) reads the public Supabase views directly and
  calls the API for chat and ingestion.
* Postgres (Supabase) with the pgvector extension stores both the relational
  data and the embeddings.
* Ollama runs `qwen2.5:14b` for generation, query rewriting, HyDE and grading,
  and `nomic-embed-text` for the 768-dimensional embeddings.

The schema, the SQL views and the row-level-security rules are all versioned
with Alembic, so a fresh database can be rebuilt with a single command.

## Project layout

```
.
├── app/                        FastAPI application
│   ├── main.py                 entry point (uvicorn app.main:app)
│   ├── config.py  db.py        env config, SQLAlchemy engine/session
│   ├── models.py               SQLAlchemy models (analytics_* + rag_*)
│   ├── ingestion/              paste, parser, normalizer, DB write
│   │   └── parsers/            Reddit and X paste parsers
│   ├── rag/                    pipeline, retriever (hybrid + RRF), embedder,
│   │                           reranker (bge-reranker-v2-m3), query expander
│   └── routers/                /api/chat/, /api/rag/feedback/, /api/ingest/
├── scripts/                    batch entry points (python -m scripts.<name>)
│   ├── ingest.py               manual paste from file or stdin
│   ├── process_posts.py        sentiment + topics + language + district
│   ├── embed_posts.py          nomic-embed-text into rag_postembedding
│   ├── compute_scores.py       per-district scores into analytics_districtscore
│   ├── pipeline.py             process, embed and score, chained
│   ├── eval_rag.py             retrieval evaluation with ablations
│   ├── generate_synthetic.py   agentic synthetic post generator (Ollama)
│   └── insert_synthetic.py     JSONL to Supabase bulk insert
├── interpreters/               HF sentiment (XLM-R), zero-shot topics
│                               (mDeBERTa), spaCy NER
├── synthetic/                  generator engine + Bucharest taxonomy/streets
├── geo/                        Overpass + Nominatim helpers (quarter seeds)
├── scrapers/                   legacy scrapers (Reddit/Maps/FB), optional
├── alembic/                    migrations: 0001 schema, 0002 views + RLS
├── eval/                       golden_set.json (results/ is gitignored)
├── tests/                      pytest unit suite (no DB or Ollama needed)
└── frontend-react/             React 19 + Vite + Tailwind dashboard
```

## Running it with Docker

```bash
# 1. Fill in DB credentials (Supabase pooler or local Postgres)
vi .env

# 2. Ollama on the host, with the two models pulled
ollama pull qwen2.5:14b
ollama pull nomic-embed-text
ollama serve

# 3. Build and run the web service and the frontend
docker compose up --build
# FastAPI  http://localhost:8000/docs
# React    http://localhost:5173/
```

To use a local Postgres instead of Supabase (`pgvector/pgvector:pg16`):

```bash
docker compose --profile localdb up postgres web
# then: alembic upgrade head   (creates tables, views and grants)
```

## Running it without Docker

```powershell
# Backend
py -m pip install -r requirements.txt
py -m spacy download ro_core_news_sm     # Romanian NER, optional but better
py -m uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend-react
npm install
npm run dev                              # http://localhost:5173/
```

## Environment variables (`.env`)

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

The React app reads its own keys from `frontend-react/.env`:
`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_AUTH0_*` and `VITE_API_URL`
(the FastAPI origin, default `http://localhost:8000`).

## Data pipeline

```powershell
# Add a post: paste UI (sidebar, Add Post), or the API, or the CLI
py -m scripts.ingest --source reddit --file post.txt

# NLP + embeddings + district scores for everything new
py -m scripts.pipeline
# or run the individual steps:
py -m scripts.process_posts            # sentiment/topics/language/district
py -m scripts.embed_posts              # pgvector embeddings via Ollama
py -m scripts.compute_scores --days 30 # per-quarter scores and grades

# Generate synthetic civic posts (agentic draft/critique/revise loop)
py -m scripts.generate_synthetic --count 100
```

Posts added through the dashboard's **Add Post** modal (or `POST /api/ingest/`)
are processed automatically: the endpoint starts `scripts.pipeline` in the
background, so the sentiment, topic, quarter and embedding appear without any
manual step.

## The RAG assistant

`POST /api/chat/` streams NDJSON events through this pipeline:

1. **Intent detection.** Explicit positive/negative phrasing and quarter names
   in the question become retrieval filters.
2. **Query rewrite** (qwen2.5:14b) into a standalone search phrase.
3. **HyDE.** A hypothetical post is generated and embedded alongside the query.
4. **Hybrid retrieval.** Dense (pgvector HNSW, cosine) plus sparse (Postgres
   full-text), fused with Reciprocal Rank Fusion and re-weighted by accumulated
   thumbs up/down feedback.
5. **Cross-encoder rerank** with the local BAAI/bge-reranker-v2-m3.
6. **Self-RAG context grading.** A weak context triggers one refined
   re-retrieval round.
7. **Streamed answer** with numbered citations and a final grounding grade.

## Evaluation

```powershell
py -m scripts.eval_rag --variants full,no-hyde,no-rerank,dense,sparse --judge
```

Replays `eval/golden_set.json` (24 label-tagged questions) through the retrieval
stack with stages ablated, reporting precision@k, hit@k, MRR and an optional LLM
context grade. JSON and Markdown reports are written to `eval/results/`.

## Tests

```powershell
py -m pytest tests/        # 32 unit tests, no DB or Ollama required
```

## Endpoints and pages

### FastAPI (`localhost:8000`)

| Path                      | What                                           |
|---------------------------|------------------------------------------------|
| `POST /api/chat/`         | streaming NDJSON RAG answer                    |
| `POST /api/rag/feedback/` | thumbs up/down on an answer                    |
| `POST /api/ingest/`       | manual paste ingestion (+ background pipeline) |
| `GET /healthz`            | liveness probe                                 |
| `GET /docs`               | OpenAPI UI                                      |

### React (`localhost:5173`)

| Path                   | What                                           |
|------------------------|------------------------------------------------|
| `/`                    | landing page (Auth0 sign-in)                   |
| `/dashboard`           | overview, KPI cards and recent feedback        |
| `/dashboard/heatmap`   | quarter polygons shaded by sentiment (Leaflet) |
| `/dashboard/topics`    | topic explorer                                 |
| `/dashboard/live-feed` | filterable feedback grid                       |
| `/dashboard/assistant` | assistant chat (citations, see-posts)          |
| `/dashboard/settings`  | preferences                                    |

## Data model

```
District (kind: city | sector | quarter; boundary_geojson, centroids)
   parent -> District (city -> sectors -> quarters)

SocialPost (district FK, sentiment, topic_scores, language, extra_data)
   topics  M2M  TopicCategory (infrastructure, cleanliness, safety,
                               transport, greenspace, other)
   rag_postembedding (vector(768), HNSW index)

DistrictScore  per (district, period): avg sentiment, issue count,
               0-10 composite, A-F grade, topic breakdown
RagFeedback    thumbs up/down per answer; re-weights future retrieval

SQL views (anon can SELECT only; everything else is RLS-denied):
   feedbacks, feedbacks_overview, feedbacks_topics, quarters_map
```

## Stack

* **Backend:** FastAPI, SQLAlchemy 2, Alembic, Postgres (Supabase) + pgvector.
* **NLP:** `cardiffnlp/twitter-xlm-roberta-base-sentiment`,
  `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` (zero-shot topics),
  spaCy `ro_core_news_sm` (NER).
* **RAG:** `nomic-embed-text` embeddings, Postgres FTS, RRF,
  `BAAI/bge-reranker-v2-m3` cross-encoder, `qwen2.5:14b` for
  generation/rewrite/HyDE/grading, all local via Ollama.
* **Frontend:** React 19, Vite, Tailwind, react-leaflet, Auth0, supabase-js.
