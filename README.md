# CivicPulse — Bucharest Civic Sentiment Tracker

Bachelor's thesis project. Aggregates civic posts from Reddit and X (Twitter)
about Bucharest, runs them through a local NLP pipeline (sentiment + topic
classification) and a local LLM extractor (qwen2.5:7b via Ollama), and serves
the results on a React dashboard backed by a Django ingestion layer, keyed
off the city's 80+ traditional quarters (cartiere) plus its six sectors.

## Architecture

```
                        ┌─────────────────────┐
                        │     Supabase        │
                        │     Postgres        │
                        │                     │
                        │ ┌─────────────────┐ │
                        │ │ analytics_*     │ │ ←── Django write
                        │ └─────────────────┘ │
                        │ ┌─────────────────┐ │
                        │ │ feedbacks (view)│ │ ←── React read (anon role)
                        │ └─────────────────┘ │
                        └──────────▲──────────┘
                                   │
            ┌──────────────────────┴──────────────────────┐
            │                                             │
   ┌────────▼────────┐                           ┌────────▼────────┐
   │   Django :8000  │                           │   React :5173   │
   │                 │                           │   (UrbanPulse)  │
   │ /admin/         │                           │                 │
   │ /ingest/   ◀──── "Add Post" link in nav ────│   Sidebar       │
   │ /feed/          │                           │   /dashboard    │
   │ /feed/map/ ◀──── iframe ────────────────────│   /heatmap      │
   │ /api/...        │                           │   /topics       │
   │                 │                           │   /live-feed    │
   │ Ollama qwen2.5  │                           │   Auth0 login   │
   └─────────────────┘                           └─────────────────┘
```

The Django side owns ingestion + heavy data work (LLM cleanup, NLP, Bucharest
quarter assignment, the canonical map view). The React side owns the user-
facing dashboard. They share Supabase as their single source of truth: Django
writes the underlying tables, React reads through a SQL view (`feedbacks`)
that translates field shapes — no duplicated state.

## Modules at a glance

```
social_mood_meter/
├── api/                          REST endpoints (DRF)
├── backend/
│   ├── apps/
│   │   ├── analytics/            SocialPost / District models, feed + map
│   │   │   ├── bucharest_quarters.py  Canonical 83-quarter list + aliases
│   │   │   └── management/commands/seed_bucharest_quarters.py
│   │   ├── ingestion/            Manual paste → parser → normalizer → DB
│   │   │   ├── parsers/          Reddit & X paste parsers
│   │   │   ├── normalizer.py     URL/emoji/diacritic cleaner
│   │   │   ├── llm_extractor.py  qwen2.5:7b structured extraction
│   │   │   ├── reprocess.py      Quarter > sector > city assignment
│   │   │   └── services.py       paste → SocialPost orchestration
│   │   ├── core/ users/ authentication/
│   │   └── ...
│   ├── config/                   Django settings, urls, wsgi/asgi
│   └── manage.py
├── frontend/
│   ├── templates/
│   │   ├── analytics/            feed.html, map.html (Leaflet quarters)
│   │   └── ingestion/paste.html  Manual paste UI
│   └── static/                   CSS, JS
├── Licenta/
│   ├── urban-sentiment/          React 19 + Vite + Tailwind dashboard
│   │   ├── src/
│   │   │   ├── App.jsx           Router + Auth0 wrapper
│   │   │   ├── components/       Sidebar, Layout
│   │   │   └── pages/            Overview, Heatmap, Topics, LiveFeed,
│   │   │                          Settings, EditProfile, LandingPage
│   │   ├── supabase/             RLS scripts + legacy schema
│   │   └── Dockerfile
│   └── desktop_*.html            Original Tailwind / "City Pulse" mockups
├── geo/                          Overpass + geocoder helpers
├── interpreters/                 HuggingFace sentiment + topic + NER
├── scrapers/                     Reddit/Google Maps/Facebook scrapers
├── Dockerfile                    Python 3.11 app image
├── docker-compose.yml            web + frontend + redis (+ opt profiles)
└── requirements.txt
```

## Quickstart (Docker — full stack)

Spins up Django + the React dashboard + redis with one command:

```bash
# 1. Fill in DB credentials (Supabase pooler or local Postgres)
vi .env

# 2. Make sure Ollama is running on the host with qwen2.5:7b pulled
ollama pull qwen2.5:7b
ollama serve

# 3. Build + run web + frontend
docker compose up --build
# → Django   http://localhost:8000/feed/    (admin + ingestion)
# → React    http://localhost:5173/         (UrbanPulse dashboard)
```

The `web` service:

- Listens on **`localhost:8000`** (homepage redirects to `/feed/`).
- Auto-applies migrations on boot (`manage.py migrate --noinput`),
  including migration `analytics/0003_feedbacks_view` that installs
  the SQL view the React reads from.
- Reads DB credentials from `.env`. Supabase by default; flip
  `USE_SQLITE=1` for an in-container SQLite file.
- Talks to **Ollama on the host machine** via
  `host.docker.internal:11434` (the compose file wires this for you).

The `frontend` service:

- Listens on **`localhost:5173`** with Vite hot-reload.
- Reads `Licenta/urban-sentiment/.env` for Auth0 + Supabase keys.
- Iframes Django's `/feed/map/` for the City Heatmap page (controlled
  by `VITE_DJANGO_URL`).
- Provides an **Add Post** button in the sidebar that opens Django's
  `/ingest/` paste form in a new tab.
  Make sure the host has `ollama serve` running and `qwen2.5:7b`
  pulled (`ollama pull qwen2.5:7b`).

### Compose profiles (opt-in services)

| Profile     | What it runs                                              | Use when… |
|-------------|-----------------------------------------------------------|-----------|
| _(default)_ | `web` + `redis`                                           | day-to-day dev |
| `localdb`   | Adds a local Postgres instead of Supabase                 | offline / CI |
| `pipeline`  | One-shot worker: migrate → seed quarters → reprocess → NLP| first-time data load |
| `celery`    | Celery worker against redis                               | scheduled pipeline runs |

Examples:

```bash
# Local Postgres (no Supabase needed)
docker compose --profile localdb up postgres web

# Run the full data pipeline once and exit
docker compose --profile pipeline up worker

# Web + scheduled worker
docker compose --profile celery up web celery
```

### Without Docker (host Python + Node)

```powershell
# Backend ----------------------------------
cd backend
py -m pip install -r ..\requirements.txt
py manage.py migrate
py manage.py seed_bucharest_quarters
py manage.py runserver           # → http://127.0.0.1:8000/feed/

# Frontend (separate terminal) -------------
cd ..\Licenta\urban-sentiment
npm install
npm run dev                      # → http://localhost:5173/
```

The two run independently and talk to the same Supabase project.

## Required env vars (`.env`)

The committed `.env` documents every setting. Minimum to boot:

```env
USE_SQLITE=1                        # 0 = use Postgres / Supabase

# Supabase (only when USE_SQLITE=0)
DB_HOST=aws-1-eu-west-1.pooler.supabase.com
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres.<your-project-ref>
DB_PASSWORD=<your-supabase-db-password>

# Ollama (host machine — leave the docker.internal alias when in compose)
OLLAMA_HOST=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5:7b
LLM_EXTRACTOR_MODEL=qwen2.5:7b

# Django
DJANGO_SECRET_KEY=change-me-to-a-random-string
```

## Common operations

```powershell
# 1. Add a post by paste (UI)
#    → http://localhost:8000/ingest/

# 2. Re-extract metadata + generate titles for all stored posts
py manage.py reprocess_with_llm --force

# 3. Refresh the Bucharest quarter / sector / city seed
py manage.py seed_bucharest_quarters         # one Overpass call + fallbacks
py manage.py seed_bucharest_quarters --skip-osm

# 4. Run the NLP pipeline (sentiment + topics + geo) on unprocessed rows
py manage.py run_pipeline --process-only
```

## URLs

### Django (`localhost:8000`)

| Path                         | What                                  |
|------------------------------|---------------------------------------|
| `/`                          | Redirects to `/feed/`                 |
| `/feed/`                     | Resident feed (filterable by source / quarter / search) |
| `/feed/map/`                 | Leaflet map of Bucharest quarters (X-Frame-Options exempt — iframable) |
| `/feed/api/quarters.geojson` | GeoJSON consumed by the map           |
| `/ingest/`                   | Manual paste UI                       |
| `/api/ingest/`               | `POST` endpoint for the paste API     |
| `/api/posts/`                | DRF browsable API for SocialPost      |
| `/admin/`                    | Django admin                          |

### React (`localhost:5173`)

| Path                         | What                                  |
|------------------------------|---------------------------------------|
| `/`                          | Landing page (Auth0 sign-in)          |
| `/dashboard`                 | Overview — KPI cards + recent feedback|
| `/dashboard/heatmap`         | City Heatmap (iframes Django's map)   |
| `/dashboard/topics`          | Topic Explorer                        |
| `/dashboard/live-feed`       | Real-time feedback grid               |
| `/dashboard/settings`        | User preferences                      |

## Data model

```
District (kind ∈ {city, sector, quarter})
   └─ parent → District (city → sectors → quarters)

SocialPost
   └─ district → District (resolved by reprocess.py:
                            quarter > sector > city)

feedbacks (SQL view, public schema)
   ← projection over SocialPost ⨝ District for the React frontend.
     Translates -1..+1 sentiment_score → 0..100, picks a Tailwind
     colour from source, formats author_initials, etc. Read-only;
     writes go through Django.
```

## Stack

- **Backend** Django 4.2, DRF, Postgres (Supabase or local).
- **NLP**     `cardiffnlp/twitter-xlm-roberta-base-sentiment` for sentiment,
              `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` for zero-shot topics,
              spaCy `ro_core_news_sm` for NER.
- **LLM**     `qwen2.5:7b` (manual paste cleanup, title generation) and
              optionally `gemma3:1B` (per-district insights) via local Ollama.
- **Geo**     Nominatim (geocoding) + Overpass API (quarter centroids) +
              Leaflet / OpenStreetMap tiles for the map view.
- **Frontend** Server-rendered Django templates + Leaflet.js; vanilla JS
              for the paste form.
