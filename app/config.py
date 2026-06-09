"""Application configuration, loaded from the project-root .env.

Keeps the same DB_* / OLLAMA_* / SUPABASE_* variable names the previous Django
backend used, so existing .env files keep working. Exposes a ready-built
SQLAlchemy DATABASE_URL with the password URL-encoded.
"""

import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


# --- Database ---------------------------------------------------------------
DB_NAME = os.environ.get("DB_NAME", "postgres")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")

# Allow a full override; otherwise assemble from the DB_* parts (password
# URL-encoded because it may contain &, comma, % etc.).
DATABASE_URL = os.environ.get("DATABASE_URL") or (
    f"postgresql+psycopg2://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"
)

# Supabase REST (used by some batch scripts; not required by the web app).
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")


# --- Retrieval --------------------------------------------------------------
# pgvector HNSW search breadth. The default (40) is too low once a WHERE filter
# (district / date) prunes candidates — filtered searches then return far fewer
# rows than requested. 200 keeps recall high for filtered queries.
HNSW_EF_SEARCH = int(os.environ.get("HNSW_EF_SEARCH", "200"))

# --- Ollama / models --------------------------------------------------------
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
CHAT_MODEL = os.environ.get("OLLAMA_CHAT_MODEL", os.environ.get("OLLAMA_MODEL", "qwen2.5:14b"))
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
RERANKER_MODEL = os.environ.get("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")

# --- CORS -------------------------------------------------------------------
# Comma-separated list of allowed origins for the SPA; "*" in dev.
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
