"""Manual paste ingestion (replaces the former Django /ingest/ web form).

Reads a pasted Reddit or X post from a file or stdin, parses + normalizes it,
and persists it to analytics_socialpost. The NLP pipeline (sentiment/topic) and
embedding run separately (scripts.embed_posts and the NLP reprocess step).

Usage:
    python -m scripts.ingest --source reddit --file post.txt
    python -m scripts.ingest --source x < tweet.txt
    echo "pasted content" | python -m scripts.ingest --source reddit
"""

import argparse
import sys

from app.ingestion.service import ingest_post, IngestionError


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True, choices=["reddit", "x"], help="Post source")
    ap.add_argument("--file", help="Path to a file with the pasted content (default: stdin)")
    args = ap.parse_args()

    raw = open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read()
    if not raw.strip():
        raise SystemExit("No input provided.")

    try:
        result = ingest_post(args.source, raw)
    except IngestionError as e:
        raise SystemExit(f"Ingestion rejected: {e}")

    verb = "created" if result.created else "already existed (updated metadata)"
    print(f"Post #{result.post_id} {verb} [{result.source}]")
    print(f"  content: {result.content[:120]}…")
    print("\nNext: run `python -m scripts.embed_posts` to index it for RAG.")


if __name__ == "__main__":
    main()
