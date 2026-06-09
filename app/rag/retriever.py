"""Hybrid retrieval: dense (pgvector cosine) + sparse (Postgres FTS), RRF-fused,
then re-weighted by accumulated thumbs up/down feedback.

Uses SQLAlchemy Core (text()) against the Supabase Postgres connection.
"""

import logging

from sqlalchemy import text

from ..config import HNSW_EF_SEARCH
from ..db import engine, SessionLocal

logger = logging.getLogger(__name__)

RRF_K = 60
MAX_CANDIDATES = 50


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


def _filter_sql(filters: dict, params: dict) -> str:
    """Append quarter/date/sentiment conditions; mutate params; return SQL fragment."""
    filters = filters or {}
    frag = ""

    # Multiple quarters from the dashboard's checkbox filter. Parameterised as
    # numbered binds (:district_0, …) so it's injection-safe and driver-agnostic.
    districts = filters.get("districts")
    if isinstance(districts, (list, tuple)) and districts:
        keys = []
        for i, name in enumerate(districts):
            k = f"district_{i}"
            params[k] = name
            keys.append(f":{k}")
        frag += f" AND d.name IN ({', '.join(keys)})"

    # Single district (kept for backward compatibility with internal callers).
    district = filters.get("district")
    if district and district != "all":
        frag += " AND d.name = :district"
        params["district"] = district

    # Date range. `from`/`since` are interchangeable lower bounds; `to` is the
    # optional upper bound. Both compare against the post's effective date.
    since = filters.get("from") or filters.get("since")
    if since:
        frag += " AND COALESCE(p.original_date, p.scraped_at) >= :since"
        params["since"] = since
    until = filters.get("to")
    if until:
        frag += " AND COALESCE(p.original_date, p.scraped_at) <= :until"
        params["until"] = until

    sentiment = filters.get("sentiment")
    if sentiment in ("Positive", "Negative", "Neutral"):
        frag += " AND p.sentiment_label = :sentiment"
        params["sentiment"] = sentiment

    # Location named in the question (detected in the pipeline). Matches either
    # the assigned district or the free-text location_name.
    location = filters.get("location")
    if location:
        frag += " AND (d.name = :location OR p.location_name = :location)"
        params["location"] = location

    return frag


# ---------------------------------------------------------------------------
# Known locations (districts + free-text location names), cached per process,
# used by the pipeline to detect a place mentioned in the user's question.
# ---------------------------------------------------------------------------
import threading  # noqa: E402

_loc_lock = threading.Lock()
_known_locations = None  # list[(lowercase, canonical)] sorted longest-first


def known_locations() -> list[tuple[str, str]]:
    global _known_locations
    if _known_locations is not None:
        return _known_locations
    with _loc_lock:
        if _known_locations is not None:
            return _known_locations
        names = []
        try:
            with engine.connect() as conn:
                names = conn.execute(text(
                    "SELECT DISTINCT name FROM analytics_district WHERE COALESCE(name,'') <> '' "
                    "UNION "
                    "SELECT DISTINCT location_name FROM analytics_socialpost "
                    "WHERE COALESCE(location_name,'') <> ''"
                )).scalars().all()
        except Exception:
            logger.exception("known_locations load failed")
        uniq = {n.strip() for n in names if n and len(n.strip()) >= 3}
        _known_locations = sorted(((n.lower(), n) for n in uniq), key=lambda x: len(x[0]), reverse=True)
        return _known_locations


_COLUMNS = """
    p.id,
    p.content,
    -- Prefer the matched district (quarter/sector); fall back to the free-text
    -- location extracted from the post (street/landmark not in analytics_district),
    -- and only then to the city default.
    COALESCE(d.name, NULLIF(p.location_name, ''), 'București') AS location,
    COALESCE(
        (SELECT tc.name
         FROM   analytics_socialpost_topics spt
         JOIN   analytics_topiccategory tc ON tc.id = spt.topiccategory_id
         WHERE  spt.socialpost_id = p.id
         ORDER  BY tc.id LIMIT 1),
        'general'
    )                               AS topic,
    COALESCE(NULLIF(p.sentiment_label,''), 'Neutral') AS sentiment_label,
    COALESCE(NULLIF(p.author,''), 'anonymous')        AS author,
    COALESCE(p.url, '')                               AS url,
    COALESCE(p.original_date, p.scraped_at)::text     AS created_at
"""


def dense_search(query_vec: list[float], filters: dict, limit: int = MAX_CANDIDATES) -> list[dict]:
    if not query_vec:
        return []
    params = {"vec": _vec_literal(query_vec), "limit": limit}
    where = _filter_sql(filters, params)
    sql = text(f"""
        SELECT {_COLUMNS},
               (1 - (pe.embedding <=> CAST(:vec AS vector))) AS score
        FROM   rag_postembedding pe
        JOIN   analytics_socialpost p   ON pe.post_id = p.id
        LEFT   JOIN analytics_district d ON d.id = p.district_id
        WHERE  pe.embedding IS NOT NULL {where}
        ORDER  BY pe.embedding <=> CAST(:vec AS vector)
        LIMIT  :limit
    """)
    try:
        # SET LOCAL needs a transaction; raise ef_search so the HNSW scan returns
        # the full LIMIT even after the WHERE filter prunes candidates.
        with engine.begin() as conn:
            conn.execute(text(f"SET LOCAL hnsw.ef_search = {int(HNSW_EF_SEARCH)}"))
            rows = conn.execute(sql, params).mappings().all()
            return [dict(r) for r in rows]
    except Exception:
        logger.exception("dense_search failed")
        return []


def sparse_search(query: str, filters: dict, limit: int = MAX_CANDIDATES) -> list[dict]:
    query = (query or "").strip()
    if not query:
        return []
    params = {"q": query, "limit": limit}
    where = _filter_sql(filters, params)
    sql = text(f"""
        SELECT {_COLUMNS},
               ts_rank_cd(to_tsvector('simple', p.content),
                          plainto_tsquery('simple', :q)) AS score
        FROM   analytics_socialpost p
        LEFT   JOIN analytics_district d ON d.id = p.district_id
        WHERE  to_tsvector('simple', p.content) @@ plainto_tsquery('simple', :q) {where}
        ORDER  BY score DESC
        LIMIT  :limit
    """)
    try:
        with engine.connect() as conn:
            rows = conn.execute(sql, params).mappings().all()
            return [dict(r) for r in rows]
    except Exception:
        logger.exception("sparse_search failed")
        return []


def rrf_fusion(dense: list[dict], sparse: list[dict], k: int = RRF_K, limit: int = MAX_CANDIDATES) -> list[dict]:
    scores: dict[int, float] = {}
    by_id: dict[int, dict] = {}
    for ranked in (dense, sparse):
        for rank, doc in enumerate(ranked):
            did = doc["id"]
            by_id[did] = doc
            scores[did] = scores.get(did, 0.0) + 1.0 / (k + rank + 1)
    order = sorted(by_id, key=lambda did: scores[did], reverse=True)
    result = [by_id[did] for did in order[:limit]]
    for doc in result:
        doc["rrf_score"] = scores[doc["id"]]
    return result


def _load_feedback_sets() -> tuple[set[int], set[int]]:
    """Net thumbs per post → (liked_ids, disliked_ids)."""
    net: dict[int, int] = {}
    try:
        with SessionLocal() as s:
            rows = s.execute(text(
                "SELECT retrieved_post_ids, rating FROM rag_feedback ORDER BY created_at DESC LIMIT 5000"
            )).all()
        for ids, rating in rows:
            if not isinstance(ids, list):
                continue
            delta = 1 if rating == "up" else -1
            for i in ids:
                try:
                    net[int(i)] = net.get(int(i), 0) + delta
                except (TypeError, ValueError):
                    continue
    except Exception:
        logger.exception("_load_feedback_sets failed")
        return set(), set()
    return ({pid for pid, s in net.items() if s > 0},
            {pid for pid, s in net.items() if s < 0})


def apply_feedback_boost(results: list[dict]) -> list[dict]:
    if not results:
        return results
    liked, disliked = _load_feedback_sets()
    if not liked and not disliked:
        return results
    liked_docs = [r for r in results if r["id"] in liked]
    neutral = [r for r in results if r["id"] not in liked and r["id"] not in disliked]
    disliked_docs = [r for r in results if r["id"] in disliked]
    return liked_docs + neutral + disliked_docs


def hybrid_search(query: str, query_vec: list[float] | None, filters: dict | None = None,
                  limit: int = MAX_CANDIDATES) -> list[dict]:
    filters = filters or {}
    dense = dense_search(query_vec, filters, limit) if query_vec else []
    sparse = sparse_search(query, filters, limit)
    fused = rrf_fusion(dense, sparse, limit=limit)
    return apply_feedback_boost(fused)
