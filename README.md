# CivicPulse — Bucharest Civic Sentiment Tracker

Bachelor's thesis project. Aggregates civic posts from Reddit and X (Twitter)
about Bucharest, runs them through a local NLP pipeline (sentiment + topic
classification) and a local LLM extractor (qwen2.5:7b via Ollama), and serves
the results on a feed + Leaflet map keyed off the city's 80+ traditional
quarters (cartiere) plus its six sectors.

## Modules at a glance

```
social_mood_meter/
├── api/                         REST endpoints (DRF)
├── backend/
│   ├── apps/
│   │   ├── analytics/           SocialPost / District models, feed + map views
│   │   ├── ingestion/           Manual paste → parser → normalizer → DB
│   │   │   ├── parsers/         Reddit & X paste parsers
│   │   │   ├── normalizer.py    URL/emoji/diacritic cleaner
│   │   │   ├── llm_extractor.py qwen2.5:7b structured extraction
│   │   │   ├── reprocess.py     Quarter > sector > city assignment
│   │   │   └── services.py      paste → SocialPost orchestration
│   │   ├── core/ users/ authentication/
│   │   └── ...
│   ├── config/                  Django settings, urls, wsgi/asgi
│   └── manage.py
├── frontend/
│   ├── templates/
│   │   ├── analytics/           feed.html, map.html
│   │   └── ingestion/paste.html Manual paste UI
│   └── static/                  CSS, JS
├── geo/                         Overpass + geocoder helpers
├── interpreters/                HuggingFace sentiment / topic / NER + Ollama summarizer
├── scrapers/                    Reddit/Google Maps/Facebook scrapers (optional)
├── Dockerfile                   App image (Python 3.11)
├── docker-compose.yml           web + redis + opt postgres / pipeline / celery
└── requirements.txt
```

## Quickstart (Docker)

The fastest path to a running stack:

```bash
# 1. Configure env (copy the template, fill in DB password if using Supabase)
cp .env .env.local && vi .env

# 2. Build + run the web service
docker compose up --build web
# → app on http://localhost:8000/feed/
```

The default `web` service:

- Listens on **`localhost:8000`** (homepage redirects to `/feed/`).
- Auto-applies migrations on boot (`manage.py migrate --noinput`).
- Reads DB credentials from `.env`. Supabase by default; flip
  `USE_SQLITE=1` for an in-container SQLite file.
- Talks to **Ollama on the host machine** via
  `host.docker.internal:11434` (the compose file wires this for you).
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

### Without Docker (host Python)

```powershell
# From the repo root
cd backend
py -m pip install -r ..\requirements.txt
py manage.py migrate
py manage.py seed_bucharest_quarters
py manage.py runserver
```

Then http://127.0.0.1:8000/feed/.

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

| Path                       | What                                  |
|----------------------------|---------------------------------------|
| `/`                        | Redirects to `/feed/`                 |
| `/feed/`                   | Resident feed (filterable by source / quarter / search) |
| `/feed/map/`               | Leaflet map of Bucharest quarters     |
| `/feed/api/quarters.geojson` | GeoJSON consumed by the map         |
| `/ingest/`                 | Manual paste UI                       |
| `/api/ingest/`             | `POST` endpoint for the paste API     |
| `/api/posts/`              | DRF browsable API for SocialPost      |
| `/admin/`                  | Django admin                          |

## Data model

```
District (kind ∈ {city, sector, quarter})
   └─ parent → District (city → sectors → quarters)

SocialPost
   └─ district → District (resolved by reprocess.py:
                            quarter > sector > city)
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
