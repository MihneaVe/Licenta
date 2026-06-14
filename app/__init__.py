"""UrbanPulse FastAPI backend (replaces the former Django backend).

Serves the City Assistant RAG endpoints and owns the SQLAlchemy models +
Alembic migrations for the Supabase Postgres schema. Batch jobs (embedding,
ingestion, NLP reprocessing) live in ../scripts as standalone CLIs.
"""
