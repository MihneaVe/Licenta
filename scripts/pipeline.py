"""Run the full data pipeline: NLP process → embed → score districts.

Chains the three batch steps so freshly-ingested posts (scripts.ingest, the
/api/ingest/ endpoint, or scripts.insert_synthetic) become fully usable by the
dashboard and the RAG assistant in one command:

1. scripts.process_posts - sentiment, topics, language, district assignment
2. scripts.embed_posts   - nomic-embed-text embeddings into rag_postembedding
3. scripts.compute_scores - per-district scores into analytics_districtscore

Usage (from the project root):
    python -m scripts.pipeline                # process new posts end-to-end
    python -m scripts.pipeline --force        # re-process + re-embed everything
    python -m scripts.pipeline --skip-embed   # no Ollama available
    python -m scripts.pipeline --days 7       # weekly scoring window
"""

import argparse
import subprocess
import sys

from scripts import compute_scores, process_posts


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="Re-process + re-embed everything")
    ap.add_argument("--limit", type=int, default=0, help="Cap posts per step (0 = all)")
    ap.add_argument("--device", type=int, default=-1, help="-1 = CPU, 0+ = GPU index")
    ap.add_argument("--skip-embed", action="store_true", help="Skip the embedding step")
    ap.add_argument("--skip-scores", action="store_true", help="Skip district scoring")
    ap.add_argument("--days", type=int, default=30, help="Scoring window in days")
    args = ap.parse_args()

    print("=== Step 1/3: NLP processing ===")
    process_posts.run(force=args.force, limit=args.limit, device=args.device)

    if args.skip_embed:
        print("\n=== Step 2/3: embeddings - skipped ===")
    else:
        print("\n=== Step 2/3: embeddings ===")
        # embed_posts owns its own argparse main(); run it as a subprocess so
        # both entry points keep a single source of truth for the embed logic.
        cmd = [sys.executable, "-m", "scripts.embed_posts"]
        if args.force:
            cmd.append("--all")
        if args.limit:
            cmd += ["--limit", str(args.limit)]
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print("Embedding step failed - fix Ollama and re-run "
                  "`python -m scripts.embed_posts`. Continuing to scoring.")

    if args.skip_scores:
        print("\n=== Step 3/3: district scores - skipped ===")
    else:
        print("\n=== Step 3/3: district scores ===")
        compute_scores.run(days=args.days)

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
