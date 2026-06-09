"""Embed social posts into rag_postembedding via Ollama nomic-embed-text.

Resumable — skips posts that already have an embedding unless --all is passed.

Usage (from the project root):
    python -m scripts.embed_posts                # embed missing posts
    python -m scripts.embed_posts --all          # re-embed everything
    python -m scripts.embed_posts --limit 100    # smoke test
    python -m scripts.embed_posts --batch 64     # Ollama embed batch size
"""

import argparse
import time

from sqlalchemy import text

from app.config import OLLAMA_HOST, EMBED_MODEL
from app.db import engine
from app.rag.embedder import is_available
import requests


def _embed_batch(texts: list[str]) -> list[list[float]] | None:
    docs = [f"search_document: {t}" for t in texts]
    try:
        r = requests.post(f"{OLLAMA_HOST}/api/embed",
                          json={"model": EMBED_MODEL, "input": docs}, timeout=300)
        if r.status_code == 200:
            embs = r.json().get("embeddings")
            if embs and len(embs) == len(texts):
                return embs
    except Exception:
        pass
    out = []
    for d in docs:
        try:
            r = requests.post(f"{OLLAMA_HOST}/api/embeddings",
                              json={"model": EMBED_MODEL, "prompt": d}, timeout=120)
            r.raise_for_status()
            out.append(r.json()["embedding"])
        except Exception:
            return None
    return out


def _doc_text(row) -> str:
    parts = [row.content or ""]
    if row.location:
        parts.append(f"Location: {row.location}")
    if row.topic:
        parts.append(f"Topic: {row.topic}")
    if row.sentiment_label:
        parts.append(f"Sentiment: {row.sentiment_label}")
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="Re-embed already-embedded posts")
    ap.add_argument("--batch", type=int, default=64, help="Ollama embed batch size")
    ap.add_argument("--limit", type=int, default=0, help="Stop after N posts (0 = all)")
    args = ap.parse_args()

    print(f"Checking Ollama embedding model {EMBED_MODEL!r} …")
    if not is_available():
        raise SystemExit(f"Embedding model {EMBED_MODEL!r} unreachable. Is Ollama running?")
    print("Embedder ready.")

    where = "" if args.all else "WHERE e.post_id IS NULL"
    limit = f"LIMIT {args.limit}" if args.limit else ""
    select_sql = text(f"""
        SELECT p.id, p.content, p.sentiment_label,
               COALESCE(d.name, '') AS location,
               COALESCE((SELECT tc.name FROM analytics_socialpost_topics spt
                         JOIN analytics_topiccategory tc ON tc.id = spt.topiccategory_id
                         WHERE spt.socialpost_id = p.id ORDER BY tc.id LIMIT 1), '') AS topic
        FROM analytics_socialpost p
        LEFT JOIN analytics_district d ON d.id = p.district_id
        LEFT JOIN rag_postembedding e ON e.post_id = p.id
        {where}
        ORDER BY p.id {limit}
    """)

    with engine.connect() as conn:
        rows = conn.execute(select_sql).all()

    total = len(rows)
    if total == 0:
        print("Nothing to embed. All caught up.")
        return
    print(f"Embedding {total} posts with {EMBED_MODEL} (batch={args.batch}) …")

    upsert = text("""
        INSERT INTO rag_postembedding (post_id, embedding, model_name)
        VALUES (:pid, CAST(:emb AS vector), :model)
        ON CONFLICT (post_id) DO UPDATE
            SET embedding = EXCLUDED.embedding, model_name = EXCLUDED.model_name, updated_at = NOW()
    """)

    ok = failed = 0
    start = time.time()
    with engine.begin() as conn:
        for i in range(0, total, args.batch):
            chunk = rows[i:i + args.batch]
            vecs = _embed_batch([_doc_text(r) for r in chunk])
            if vecs is None:
                failed += len(chunk)
                continue
            for r, v in zip(chunk, vecs):
                lit = "[" + ",".join(f"{x:.8f}" for x in v) + "]"
                conn.execute(upsert, {"pid": r.id, "emb": lit, "model": EMBED_MODEL})
                ok += 1
            done = min(i + args.batch, total)
            rate = done / (time.time() - start)
            print(f"  {done}/{total} ({rate:.1f}/s) — {ok} ok, {failed} failed")

    print(f"Done! {ok} embedded, {failed} failed in {(time.time()-start)/60:.1f} min.")


if __name__ == "__main__":
    main()
