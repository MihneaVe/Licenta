"""Boost the quarters closest to flipping: push the N nearest-to-positive
quarters into green and the N nearest-to-negative into red.

"Closest" = smallest sentiment gap to the target band, so the fewest synthetic
posts are needed. For each chosen quarter the script computes how many +0.85
(or -0.85) posts move its average sentiment to a comfortable target, generates
them with the agentic engine (draft -> critique -> revise) and inserts the
accepted ones straight into Supabase (service key, bypasses RLS).

The heatmap reads AVG(sentiment_score) live from the posts table, so the colours
update as soon as the inserts land (no need to re-run compute_scores).

Usage (from the project root, Ollama running):
    python -m scripts.boost_quarters
    python -m scripts.boost_quarters --pos 3 --neg 3 --concurrency 4
    python -m scripts.boost_quarters --model qwen2.5:14b --dry-run
"""
import argparse
import json
import math
import os
import pathlib
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SUPABASE_URL = "https://ujdkiorhdynsrlkhrtcm.supabase.co"

# A quarter is "green" at avg >= POS_BAND, "red" at avg <= -POS_BAND. We pick
# quarters still outside the band and push them to TARGET (comfortably inside).
POS_BAND = 0.30
POS_TARGET = 0.40
NEG_TARGET = -0.40
POST_SCORE = 0.85          # |sentiment_score| of a generated positive/negative post
MIN_POSTS, MAX_POSTS = 15, 150

# ------------------------------------------------------------------ args
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--pos", type=int, default=3, help="How many quarters to flip green.")
ap.add_argument("--neg", type=int, default=3, help="How many quarters to flip red.")
ap.add_argument("--model", default="qwen2.5:14b")
ap.add_argument("--concurrency", type=int, default=4)
ap.add_argument("--max-revisions", type=int, default=1)
ap.add_argument("--dry-run", action="store_true",
                help="Only print the chosen quarters and post counts; generate nothing.")
args = ap.parse_args()


# ------------------------------------------------------------------ keys
def _read_env(path, key):
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith(key + "="):
            return s.split("=", 1)[1].strip()
    return None


ANON = (os.environ.get("SUPABASE_ANON_KEY")
        or _read_env(ROOT / "frontend-react" / ".env", "VITE_SUPABASE_ANON_KEY")
        or _read_env(ROOT / ".env", "SUPABASE_ANON_KEY"))
SERVICE = (os.environ.get("SUPABASE_SERVICE_KEY")
           or _read_env(ROOT / ".env", "SUPABASE_SERVICE_KEY")
           or _read_env(ROOT / ".env", "SUPABASE_SERVICE_ROLE_KEY"))
READ_KEY = ANON or SERVICE
if not READ_KEY:
    sys.exit("No Supabase key found (need SUPABASE_ANON_KEY or a service key to read quarters).")


def _sector_of(parent):
    if not parent:
        return None
    m = re.search(r"(\d+)", parent)
    return int(m.group(1)) if m else None


def fetch_quarters(key):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/quarters_map"
        "?select=id,name,post_count,parent,avg_sentiment,centroid_lat,centroid_lng",
        headers={"apikey": key, "Authorization": f"Bearer {key}"}, timeout=30)
    r.raise_for_status()
    return r.json()


# ------------------------------------------------------------------ plan
def _posts_to_flip(c, a, target, score):
    """Posts of |score| needed to move a quarter of `c` posts from avg `a` to
    `target`. Derived from (a*c + p*score) / (c + p) = target."""
    denom = score - target if target > 0 else (-score) - target
    need = c * (target - a) / denom
    return max(MIN_POSTS, min(MAX_POSTS, int(math.ceil(need))))


def choose_quarters(quarters, n_pos, n_neg):
    usable = [q for q in quarters
              if (q.get("post_count") or 0) > 0 and q.get("avg_sentiment") is not None]

    # Closest-to-positive: highest avg that is still not green (avg < POS_BAND).
    pos_cands = sorted((q for q in usable if float(q["avg_sentiment"]) < POS_BAND),
                       key=lambda q: float(q["avg_sentiment"]), reverse=True)
    pos = pos_cands[:n_pos]
    pos_names = {q["name"] for q in pos}

    # Closest-to-negative: lowest avg that is still not red (avg > -POS_BAND),
    # excluding any quarter already chosen for the positive boost.
    neg_cands = sorted((q for q in usable
                        if float(q["avg_sentiment"]) > -POS_BAND and q["name"] not in pos_names),
                       key=lambda q: float(q["avg_sentiment"]))
    neg = neg_cands[:n_neg]

    plan = []  # (name, sector, sentiment, n_posts, old_avg)
    for q in pos:
        c, a = q.get("post_count") or 0, float(q["avg_sentiment"])
        plan.append((q["name"], _sector_of(q.get("parent")), "positive",
                     _posts_to_flip(c, a, POS_TARGET, POST_SCORE), a))
    for q in neg:
        c, a = q.get("post_count") or 0, float(q["avg_sentiment"])
        plan.append((q["name"], _sector_of(q.get("parent")), "negative",
                     _posts_to_flip(c, a, NEG_TARGET, POST_SCORE), a))
    return plan


quarters = fetch_quarters(READ_KEY)
if not quarters:
    sys.exit("quarters_map returned no rows.")
plan = choose_quarters(quarters, args.pos, args.neg)
if not plan:
    sys.exit("No eligible quarters to boost (need quarters with posts and a known average).")

print("Chosen quarters:")
for name, sector, sent, p, a in plan:
    arrow = "-> green" if sent == "positive" else "-> red"
    print(f"  {name:<24} avg {a:+.2f}  {arrow}  (+{p} {sent} posts)")
total = sum(p for *_, p, _ in plan)
print(f"Total posts to generate: {total}")
if args.dry_run:
    sys.exit(0)
if not SERVICE:
    sys.exit("No service_role key (set SUPABASE_SERVICE_KEY in .env) - cannot insert.")


# ------------------------------------------------------------------ DB sink
SENT_SCORE = {"negative": -0.85, "positive": 0.85, "neutral": 0.0}
SENT_LABEL = {"negative": "Negative", "positive": "Positive", "neutral": "Neutral"}
CATS = ["infrastructure", "cleanliness", "safety", "transport", "greenspace", "other"]
SPREAD_DAYS = 60


class DBSink:
    def __init__(self, key, dmap):
        self.h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        self.dmap = dmap
        self.now = datetime.now(timezone.utc)
        self.rng = random.Random(7)
        self.inserted = 0
        requests.post(
            f"{SUPABASE_URL}/rest/v1/analytics_topiccategory?on_conflict=name",
            headers={**self.h, "Prefer": "resolution=ignore-duplicates,return=minimal"},
            data=json.dumps([{"name": c, "description": ""} for c in CATS]), timeout=30)
        r = requests.get(f"{SUPABASE_URL}/rest/v1/analytics_topiccategory?select=id,name",
                         headers=self.h, timeout=30)
        r.raise_for_status()
        self.tmap = {t["name"]: t["id"] for t in r.json()}

    def _row(self, rec):
        sent = rec["sentiment"]
        od = (self.now - timedelta(minutes=self.rng.randint(5, SPREAD_DAYS * 24 * 60))).isoformat()
        return {
            "source": rec["source"], "source_id": rec["id"], "content": rec["text"],
            "author": (rec.get("author") or "")[:255], "url": "", "location_name": rec["district"],
            "district_id": self.dmap.get(rec["district"]),
            "sentiment_score": SENT_SCORE.get(sent, 0.0),
            "sentiment_label": SENT_LABEL.get(sent, "Neutral"),
            "topic_scores": {rec["app_topic"]: 1.0},
            "score": max(int(rec.get("authenticity") or 1), 1) * self.rng.randint(3, 30),
            "extra_data": {"synthetic": {k: rec.get(k) for k in
                           ("subtopic", "app_topic", "sentiment", "angle", "authenticity", "accepted", "hashtags")},
                           "boost": True},
            "language": "en", "ingestion_method": "synthetic",
            "original_date": od, "scraped_at": self.now.isoformat(), "processed_at": self.now.isoformat(),
        }

    def insert(self, recs):
        if not recs:
            return 0
        rows = [self._row(r) for r in recs]
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/analytics_socialpost?on_conflict=source,source_id",
            headers={**self.h, "Prefer": "resolution=ignore-duplicates,return=representation"},
            data=json.dumps(rows), timeout=60)
        if resp.status_code >= 300:
            sys.stdout.write(f"\n  ! insert error {resp.status_code}: {resp.text[:160]}\n")
            return 0
        inserted = resp.json()
        app_by_sid = {r["id"]: r["app_topic"] for r in recs}
        links = [{"socialpost_id": row["id"], "topiccategory_id": self.tmap[app_by_sid[row["source_id"]]]}
                 for row in inserted if app_by_sid.get(row["source_id"]) in self.tmap]
        if links:
            requests.post(
                f"{SUPABASE_URL}/rest/v1/analytics_socialpost_topics?on_conflict=socialpost_id,topiccategory_id",
                headers={**self.h, "Prefer": "resolution=ignore-duplicates,return=minimal"},
                data=json.dumps(links), timeout=60)
        self.inserted += len(inserted)
        return len(inserted)


# ------------------------------------------------------------------ generate
from synthetic.ollama_client import OllamaClient
from synthetic.engine import SyntheticEngine
from synthetic.taxonomy import sample_specs, ANGLES

client = OllamaClient()
if not client.is_available(args.model):
    print("MODEL NOT AVAILABLE:", args.model, "| have:", client.list_models())
    sys.exit(2)

rng = random.Random(42)
dmap = {q["name"]: q["id"] for q in quarters}

# Expand the plan into one (name, sector, sentiment) entry per post.
expanded = []
for name, sector, sent, p, _a in plan:
    expanded += [(name, sector, sent)] * p
rng.shuffle(expanded)

specs = sample_specs(len(expanded), sources=["reddit", "x", "instagram", "facebook"],
                     sentiments=["positive", "negative"],
                     districts=[(n, s) for n, s, _ in expanded], rng=rng)
for spec, (name, sector, sent) in zip(specs, expanded):
    spec.district_name = name
    spec.sector = sector
    spec.sentiment = sent
    spec.angle = rng.choice(ANGLES.get(sent, ANGLES["neutral"]))
    spec.streets = None

engine = SyntheticEngine(client, args.model, max_revisions=args.max_revisions,
                         min_authenticity=3, language="English", street_max_fix=0)
sink = DBSink(SERVICE, dmap)

print(f"\nGenerating {len(specs)} posts | model={args.model} concurrency={args.concurrency} …",
      flush=True)
st = {"done": 0, "accepted": 0, "inserted": 0, "errors": 0, "t0": time.time()}
buf = []
ex = ThreadPoolExecutor(max_workers=max(1, args.concurrency))
futures = [ex.submit(engine.generate_one, s) for s in specs]
try:
    for fut in as_completed(futures):
        p = fut.result()
        st["done"] += 1
        if p.error:
            st["errors"] += 1
        elif p.accepted:
            st["accepted"] += 1
            buf.append(p.to_record())
            if len(buf) >= 50:
                st["inserted"] += sink.insert(buf)
                buf = []
        el = time.time() - st["t0"]
        rate = st["done"] / el if el else 0
        sys.stdout.write(f"\r  {st['done']}/{len(specs)} | ok {st['accepted']} "
                         f"ins {st['inserted']} err {st['errors']} | {rate:4.1f}/s   ")
        sys.stdout.flush()
except KeyboardInterrupt:
    sys.stdout.write("\n⏹  Interrupted - flushing…\n")
finally:
    ex.shutdown(wait=False, cancel_futures=True)
    st["inserted"] += sink.insert(buf)

print()
print("─" * 60)
print(f"DONE in {(time.time()-st['t0'])/60:.1f} min - inserted {st['inserted']} posts "
      f"({st['accepted']} accepted, {st['errors']} errors).")
print("The heatmap colours update live (quarters_map averages the new posts).")
