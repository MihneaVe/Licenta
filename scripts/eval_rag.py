"""Offline evaluation of the RAG retrieval stack against eval/golden_set.json.

Replays each golden question through the same retrieval components the live
pipeline uses (sentiment/location intent detection, query rewrite, HyDE,
hybrid dense+sparse search, cross-encoder rerank) and scores the result with
a label-proxy notion of relevance: a retrieved post is *relevant* when it
matches every expectation (topics / sentiment / locations) attached to the
question.

Metrics per variant:
    precision@k   mean fraction of the top-k posts that are relevant
    hit@k         fraction of questions with ≥1 relevant post in the top-k
    MRR           mean reciprocal rank of the first relevant post
    context_score mean LLM judge grade 1-5 (only with --judge)

Ablation variants (--variants, comma-separated):
    full        rewrite + HyDE + hybrid + rerank   (production pipeline)
    no-hyde     drop the hypothetical-document embedding
    no-rerank   keep RRF order, skip the cross-encoder
    no-rewrite  embed the raw question
    dense       dense retrieval only (no FTS leg)
    sparse      FTS retrieval only (no dense leg)

Results are printed as a table and written to eval/results/ as JSON + Markdown
(per-question detail included) for the thesis evaluation chapter.

Usage (Ollama must be running):
    python -m scripts.eval_rag                          # full, k=10
    python -m scripts.eval_rag --variants full,no-hyde,no-rerank
    python -m scripts.eval_rag --judge                  # add LLM context grades
    python -m scripts.eval_rag --limit 5                # smoke test
"""

import argparse
import json
import pathlib
import time
from datetime import datetime, timezone

from app.rag.embedder import average_embeddings, embed_document, embed_query
from app.rag.pipeline import detect_location_intent, detect_sentiment_intent, grade_context
from app.rag.query_expander import generate_hyde, rewrite_query
from app.rag.reranker import rerank
from app.rag.retriever import dense_search, hybrid_search, rrf_fusion, sparse_search

ROOT = pathlib.Path(__file__).resolve().parent.parent
GOLDEN_SET = ROOT / "eval" / "golden_set.json"
RESULTS_DIR = ROOT / "eval" / "results"

VARIANTS = {
    "full":       dict(rewrite=True,  hyde=True,  dense=True,  sparse=True,  rerank=True),
    "no-hyde":    dict(rewrite=True,  hyde=False, dense=True,  sparse=True,  rerank=True),
    "no-rerank":  dict(rewrite=True,  hyde=True,  dense=True,  sparse=True,  rerank=False),
    "no-rewrite": dict(rewrite=False, hyde=True,  dense=True,  sparse=True,  rerank=True),
    "dense":      dict(rewrite=True,  hyde=False, dense=True,  sparse=False, rerank=True),
    "sparse":     dict(rewrite=True,  hyde=False, dense=False, sparse=True,  rerank=True),
}

CANDIDATES = 50


def is_relevant(post: dict, expect: dict) -> bool:
    topics = expect.get("topics")
    if topics and (post.get("topic") or "") not in topics:
        return False
    sentiment = expect.get("sentiment")
    if sentiment and (post.get("sentiment_label") or "") != sentiment:
        return False
    locations = expect.get("locations")
    if locations and (post.get("location") or "") not in locations:
        return False
    return True


def retrieve(question: str, flags: dict, k: int) -> list[dict]:
    """Mirror app.rag.pipeline retrieval with individual stages toggleable."""
    filters = {}
    intent = detect_sentiment_intent(question)
    if intent:
        filters["sentiment"] = intent
    place = detect_location_intent(question)
    if place:
        filters["location"] = place

    query = rewrite_query(question) if flags["rewrite"] else question

    combined = None
    if flags["dense"]:
        q_vec = embed_query(query)
        hyde_vec = None
        if flags["hyde"]:
            hyde_doc = generate_hyde(query)
            hyde_vec = embed_document(hyde_doc) if hyde_doc else None
        combined = average_embeddings([v for v in [q_vec, hyde_vec] if v]) if q_vec else None

    if flags["dense"] and flags["sparse"]:
        candidates = hybrid_search(query, combined, filters, limit=CANDIDATES)
    elif flags["dense"]:
        candidates = rrf_fusion(dense_search(combined, filters, CANDIDATES), [], limit=CANDIDATES)
    else:
        candidates = rrf_fusion([], sparse_search(query, filters, CANDIDATES), limit=CANDIDATES)

    if flags["rerank"]:
        return rerank(query, candidates, top_k=k)
    return candidates[:k]


def evaluate_variant(name: str, questions: list[dict], k: int, judge: bool) -> dict:
    flags = VARIANTS[name]
    rows = []
    for q in questions:
        t0 = time.time()
        posts = retrieve(q["question"], flags, k)
        elapsed = time.time() - t0

        flags_rel = [is_relevant(p, q["expect"]) for p in posts]
        relevant = sum(flags_rel)
        first_hit = next((i + 1 for i, r in enumerate(flags_rel) if r), None)
        row = {
            "id": q["id"],
            "question": q["question"],
            "retrieved": len(posts),
            "relevant": relevant,
            "precision": relevant / k,
            "hit": first_hit is not None,
            "reciprocal_rank": (1.0 / first_hit) if first_hit else 0.0,
            "seconds": round(elapsed, 2),
            "post_ids": [p["id"] for p in posts],
        }
        if judge:
            row["context_score"] = grade_context(q["question"], posts)
        rows.append(row)
        mark = "+" if row["hit"] else "-"
        print(f"  [{mark}] {q['id']} p@{k}={row['precision']:.2f} rr={row['reciprocal_rank']:.2f}"
              + (f" judge={row['context_score']}" if judge else "")
              + f" ({elapsed:.1f}s) {q['question'][:60]}")

    n = len(rows)
    summary = {
        "variant": name,
        "questions": n,
        "k": k,
        f"precision@{k}": round(sum(r["precision"] for r in rows) / n, 4),
        f"hit@{k}": round(sum(1 for r in rows if r["hit"]) / n, 4),
        "mrr": round(sum(r["reciprocal_rank"] for r in rows) / n, 4),
    }
    if judge:
        summary["context_score"] = round(sum(r["context_score"] for r in rows) / n, 2)
    return {"summary": summary, "details": rows}


def write_reports(results: dict, k: int, judge: bool) -> pathlib.Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    json_path = RESULTS_DIR / f"eval_{stamp}.json"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    cols = [f"precision@{k}", f"hit@{k}", "mrr"] + (["context_score"] if judge else [])
    lines = [
        f"# RAG retrieval evaluation - {stamp}",
        "",
        f"{len(results['variants'])} variant(s), "
        f"{results['variants'][0]['summary']['questions']} questions, top-{k}.",
        "",
        "| variant | " + " | ".join(cols) + " |",
        "|---------|" + "|".join("---" for _ in cols) + "|",
    ]
    for v in results["variants"]:
        s = v["summary"]
        lines.append(f"| {s['variant']} | " + " | ".join(str(s[c]) for c in cols) + " |")
    md_path = RESULTS_DIR / f"eval_{stamp}.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--variants", default="full",
                    help=f"Comma-separated subset of: {', '.join(VARIANTS)}")
    ap.add_argument("--k", type=int, default=10, help="Posts scored per question")
    ap.add_argument("--limit", type=int, default=0, help="Only the first N questions")
    ap.add_argument("--judge", action="store_true",
                    help="Also grade context relevance with the LLM judge (slower)")
    args = ap.parse_args()

    names = [v.strip() for v in args.variants.split(",") if v.strip()]
    unknown = [v for v in names if v not in VARIANTS]
    if unknown:
        raise SystemExit(f"Unknown variant(s): {unknown}. Choose from: {list(VARIANTS)}")

    questions = json.loads(GOLDEN_SET.read_text(encoding="utf-8"))["questions"]
    if args.limit:
        questions = questions[:args.limit]

    results = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "k": args.k, "judge": args.judge, "variants": []}
    for name in names:
        print(f"\n=== Variant: {name} ({len(questions)} questions, k={args.k}) ===")
        results["variants"].append(evaluate_variant(name, questions, args.k, args.judge))

    print("\n=== Summary ===")
    for v in results["variants"]:
        print("  " + json.dumps(v["summary"], ensure_ascii=False))

    md_path = write_reports(results, args.k, args.judge)
    print(f"\nReports written to {md_path.parent} ({md_path.name} + .json)")


if __name__ == "__main__":
    main()
