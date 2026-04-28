# syntax=docker/dockerfile:1.6

# ----------------------------------------------------------------------
# CivicPulse / social_mood_meter — Django backend image
#
# Build:
#   docker build -t civicpulse:latest .
#
# Run (dev):
#   docker compose up web
#
# The container only runs the Django app. Heavy ML extras (Playwright
# + chromium for the scrapers, full spaCy model downloads) are guarded
# behind build args so the dev image stays small (~700MB instead of 4GB).
# ----------------------------------------------------------------------

FROM python:3.11-slim AS base

ARG INSTALL_PLAYWRIGHT=0
ARG INSTALL_SPACY_MODEL=0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps:
#   build-essential + libpq-dev   → psycopg2 build / Postgres client libs
#   curl                          → health checks
#   libgomp1 + libstdc++          → torch / transformers runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Python deps — copied first so the layer caches across code edits.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Optional: Playwright browsers (only the scrapers need this).
RUN if [ "$INSTALL_PLAYWRIGHT" = "1" ]; then \
        playwright install --with-deps chromium ; \
    fi

# Optional: Romanian spaCy model (used by interpreters/ner_extractor).
RUN if [ "$INSTALL_SPACY_MODEL" = "1" ]; then \
        python -m spacy download ro_core_news_sm ; \
    fi

# Project source.
COPY . .

# manage.py adds both /app and /app/backend to sys.path, so running
# from /app keeps `from api.endpoints …` and `from apps.* …` resolving.
WORKDIR /app/backend

EXPOSE 8000

# Default command — runs migrations then serves with gunicorn.
# docker-compose can override this for the `worker` profile.
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile - --error-logfile -"]
