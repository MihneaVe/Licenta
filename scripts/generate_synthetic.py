"""Synthetic civic-post generator (+ optional live Supabase insert).

Generates platform-authentic Bucharest posts via the agentic
draft -> critique -> revise loop (Ollama), spreads them across the city's
*actual* Supabase quarters - **filling the emptiest cartiere first** so the
heatmap fills in - writes one JSONL record per post, and (when a Supabase
service key is available) inserts the accepted ("good") posts into the DB as
it goes, with a live progress bar.

Examples:
    python scripts/generate_synthetic.py --count 2000 --concurrency 4
    python scripts/generate_synthetic.py --count 500 --no-insert                 # JSONL only
    python scripts/generate_synthetic.py --count 5000 --max-revisions 0 --out data/synthetic/run.jsonl

DB insert needs a service_role key (it bypasses RLS). It is read from
$SUPABASE_SERVICE_KEY or the project root .env (SUPABASE_SERVICE_KEY=...).
Without it the script still writes the JSONL and tells you how to insert
later. Ctrl+C stops cleanly: pending posts are cancelled, the buffer is
flushed, and everything generated so far is kept.
"""
import sys, os, json, time, random, pathlib, argparse, importlib.util, re, heapq
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SUPABASE_URL = "https://ujdkiorhdynsrlkhrtcm.supabase.co"

# --------------------------------------------------------------------------- args
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--count", type=int, default=40)
ap.add_argument("--model", default="qwen2.5:14b")
ap.add_argument("--max-revisions", type=int, default=1,
                help="0 = draft + one critique (fastest); 1-2 = allow rewrites.")
ap.add_argument("--concurrency", type=int, default=1,
                help="Parallel Ollama requests. Needs OLLAMA_NUM_PARALLEL>=N on the server.")
ap.add_argument("--balance", default="realistic", choices=["realistic", "balanced"])
ap.add_argument("--out", default=str(ROOT / "data" / "synthetic" / "demo.jsonl"))
ap.add_argument("--no-insert", action="store_true",
                help="Skip the live DB insert; only write the JSONL file.")
ap.add_argument("--insert-batch", type=int, default=100,
                help="How many accepted posts to buffer before each DB insert.")
ap.add_argument("--min-per-quarter", type=int, default=0,
                help="Ensure every quarter reaches at least N total posts "
                     "(fills the biggest deficits first); raises --count if needed.")
ap.add_argument("--even", action="store_true",
                help="Split --count evenly across all quarters (ignore existing "
                     "post counts) instead of filling the emptiest first.")
ap.add_argument("--positive-quarters", type=int, default=0,
                help="Bias mode: pick N currently-non-positive quarters and "
                     "generate enough POSITIVE posts to flip each one green. "
                     "Ignores --count / --even / --min-per-quarter.")
ap.add_argument("--neutral-quarters", type=int, default=0,
                help="Bias mode: pick N currently-non-neutral quarters (green or "
                     "red) and generate enough NEUTRAL posts to pull each one's "
                     "average sentiment toward amber/neutral. Mutually exclusive "
                     "with --positive-quarters; ignores --count / --even / "
                     "--min-per-quarter.")
ap.add_argument("--no-streets", action="store_true",
                help="Disable OSM real-street grounding + verification (faster, "
                     "but posts may name streets from the wrong area).")
ap.add_argument("--street-radius", type=int, default=1300,
                help="Metres around a quarter's centroid to gather its real streets.")
ap.add_argument("--street-fixes", type=int, default=2,
                help="Max LLM revise passes to correct a hallucinated street name "
                     "before the deterministic replacement kicks in.")
ap.add_argument("--mixed", action="store_true",
                help="Scene mode: give every quarter a realistic mix of ALL three "
                     "sentiments with a per-quarter LEAN - ~--pos-quarters positive, "
                     "~--neg-quarters negative, the rest neutral - topping each "
                     "quarter up to --per-quarter TOTAL posts (and guaranteeing at "
                     "least one positive/negative/neutral post per quarter). "
                     "Ignores --count / --even and the other bias modes.")
ap.add_argument("--pos-quarters", type=int, default=20,
                help="(--mixed) how many quarters lean positive / green.")
ap.add_argument("--neg-quarters", type=int, default=20,
                help="(--mixed) how many quarters lean negative / red; the rest lean neutral.")
ap.add_argument("--per-quarter", type=int, default=30,
                help="(--mixed) minimum TOTAL posts per quarter (existing + new).")
args = ap.parse_args()

from synthetic.ollama_client import OllamaClient
from synthetic.engine import SyntheticEngine
from synthetic.taxonomy import sample_specs, ANGLES


# --------------------------------------------------------------------------- keys
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
        f"{SUPABASE_URL}/rest/v1/quarters_map?select=id,name,post_count,parent,avg_sentiment,centroid_lat,centroid_lng",
        headers={"apikey": key, "Authorization": f"Bearer {key}"}, timeout=30)
    r.raise_for_status()
    return r.json()


# --------------------------------------------------------------------------- DB sink
SENT_SCORE = {"negative": -0.85, "positive": 0.85, "neutral": 0.0}
SENT_LABEL = {"negative": "Negative", "positive": "Positive", "neutral": "Neutral"}
CATS = ["infrastructure", "cleanliness", "safety", "transport", "greenspace", "other"]
SPREAD_DAYS = 60


class DBSink:
    """Inserts accepted posts into Supabase via PostgREST (service key)."""

    def __init__(self, key, dmap):
        self.h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        self.dmap = dmap
        self.now = datetime.now(timezone.utc)
        self.rng = random.Random(7)
        self.inserted = 0
        # Ensure the six topic categories exist, then map name -> id.
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
                           ("subtopic", "app_topic", "sentiment", "angle", "authenticity", "accepted", "hashtags")}},
            "language": "en", "ingestion_method": "synthetic",
            "original_date": od, "scraped_at": self.now.isoformat(), "processed_at": self.now.isoformat(),
        }

    def insert(self, recs):
        """Insert a batch; returns the number of newly-inserted rows."""
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


# --------------------------------------------------------------------------- plan + specs
rng = random.Random(42)
quarters = fetch_quarters(READ_KEY)
if not quarters:
    sys.exit("quarters_map returned no rows - is the view present and seeded?")
dmap = {q["name"]: q["id"] for q in quarters}
empty_before = sum(1 for q in quarters if not (q.get("post_count") or 0))


def build_coverage_plan(quarters, count, rng, ignore_existing=False):
    """Assign `count` posts across quarters, always topping up the one with
    the fewest next. By default that counts existing posts (so empty cartiere
    fill first); with ``ignore_existing`` every quarter starts at 0, which
    splits ``count`` evenly across all of them."""
    heap = [[0 if ignore_existing else (q.get("post_count") or 0),
             rng.random(), q["name"], _sector_of(q.get("parent"))]
            for q in quarters]
    heapq.heapify(heap)
    plan = []
    for _ in range(count):
        cur = heap[0]
        plan.append((cur[2], cur[3]))
        heapq.heapreplace(heap, [cur[0] + 1, rng.random(), cur[2], cur[3]])
    return plan


def build_positive_plan(quarters, n, rng, target=0.40, lo=25, hi=200):
    """Pick up to `n` currently-non-positive quarters (that have posts) and
    size enough +0.85 posts to push each one's average sentiment up to
    ~`target` (comfortably green, >= 0.3). Returns (plan, picks)."""
    cands = [q for q in quarters
             if (q.get("post_count") or 0) > 0
             and (q.get("avg_sentiment") is None or float(q["avg_sentiment"]) < 0.3)]
    rng.shuffle(cands)
    plan, picks = [], []
    for q in cands[:n]:
        c = q.get("post_count") or 0
        a = 0.0 if q.get("avg_sentiment") is None else float(q["avg_sentiment"])
        # +0.85 posts needed to move the average from `a` up to `target`.
        need = c * (target - a) / (0.85 - target) if a < target else lo
        p = max(lo, min(hi, int(round(need))))
        plan += [(q["name"], _sector_of(q.get("parent")))] * p
        picks.append((q["name"], c, a, p))
    rng.shuffle(plan)
    return plan, picks


def build_neutral_plan(quarters, n, rng, target_abs=0.15, lo=25, hi=200):
    """Pick up to `n` currently-non-neutral quarters (avg sentiment outside the
    amber band, |avg| >= 0.3 - i.e. clearly green or red) and size enough
    neutral (0.0) posts to dilute each one's average toward ~0 (amber).
    Returns (plan, picks).

    Neutral posts only *dilute* the mean toward zero, so strongly-skewed or
    large quarters may not fully reach neutral once the per-quarter cap (`hi`)
    kicks in - they still move clearly toward amber, mirroring the positive
    plan's behaviour."""
    cands = [q for q in quarters
             if (q.get("post_count") or 0) > 0
             and q.get("avg_sentiment") is not None
             and abs(float(q["avg_sentiment"])) >= 0.3]
    rng.shuffle(cands)
    plan, picks = [], []
    for q in cands[:n]:
        c = q.get("post_count") or 0
        a = float(q["avg_sentiment"])
        # neutral (0.0) posts needed to pull |average| from |a| down to target_abs:
        #   |a|*c / (c + p) = target_abs  =>  p = c*(|a| - target_abs)/target_abs
        need = c * (abs(a) - target_abs) / target_abs if abs(a) > target_abs else lo
        p = max(lo, min(hi, int(round(need))))
        plan += [(q["name"], _sector_of(q.get("parent")))] * p
        picks.append((q["name"], c, a, p))
    rng.shuffle(plan)
    return plan, picks


# Per-quarter sentiment mix by lean. Scores are +0.85/-0.85/0.0, so these weights
# put a positive-lean quarter's average around +0.36 (green), negative around
# -0.36 (red), and neutral around 0 (amber) - while every quarter keeps all three.
_MIX_LEAN = {
    "positive": {"positive": 0.60, "negative": 0.18, "neutral": 0.22},
    "negative": {"negative": 0.60, "positive": 0.18, "neutral": 0.22},
    "neutral":  {"neutral": 0.50, "positive": 0.25, "negative": 0.25},
}


def build_mixed_plan(quarters, pos_n, neg_n, per_quarter, rng):
    """Give every quarter a sentiment lean (~pos_n positive, ~neg_n negative, the
    rest neutral) and emit posts so each reaches `per_quarter` TOTAL posts, always
    seeding at least one positive/negative/neutral post per quarter. The per-post
    sentiment follows the quarter's lean.

    Returns (plan, sentiments, bucket_counts): plan is [(name, sector)] and
    sentiments is the aligned per-post sentiment list."""
    order = list(quarters)
    rng.shuffle(order)
    bucket = {}
    for i, q in enumerate(order):
        bucket[q["name"]] = ("positive" if i < pos_n
                             else "negative" if i < pos_n + neg_n
                             else "neutral")

    plan, sents = [], []
    for q in quarters:
        name, sector = q["name"], _sector_of(q.get("parent"))
        existing = q.get("post_count") or 0
        need = max(per_quarter - existing, 3)  # >=3 so all three types are present
        w = _MIX_LEAN[bucket[name]]
        picks = ["positive", "negative", "neutral"]  # guarantee one of each
        picks += rng.choices(list(w.keys()), weights=list(w.values()), k=max(0, need - 3))
        for s in picks:
            plan.append((name, sector))
            sents.append(s)

    idx = list(range(len(plan)))
    rng.shuffle(idx)
    plan = [plan[i] for i in idx]
    sents = [sents[i] for i in idx]
    counts = {"positive": 0, "negative": 0, "neutral": 0}
    for b in bucket.values():
        counts[b] += 1
    return plan, sents, counts


sentiments = ["negative", "positive"]
plan_sents = None  # per-post sentiments (set by --mixed)
_n_bias = sum(bool(x) for x in (args.mixed, args.positive_quarters > 0, args.neutral_quarters > 0))
if _n_bias > 1:
    sys.exit("Choose only one mode: --mixed OR --positive-quarters OR --neutral-quarters.")
if args.mixed:
    plan, plan_sents, bcounts = build_mixed_plan(
        quarters, args.pos_quarters, args.neg_quarters, args.per_quarter, rng)
    COUNT = len(plan)
    sentiments = ["negative", "positive", "neutral"]
    print(f"Mixed scene: {bcounts['positive']} positive / {bcounts['negative']} negative / "
          f"{bcounts['neutral']} neutral quarters · >= {args.per_quarter} posts/quarter · all "
          f"3 sentiments each -> {COUNT} new posts.", flush=True)
elif args.positive_quarters > 0:
    plan, picks = build_positive_plan(quarters, args.positive_quarters, rng)
    if not plan:
        sys.exit("No non-positive quarters with posts to flip.")
    COUNT = len(plan)
    sentiments = ["positive"]
    print(f"Positive-bias mode: flipping {len(picks)} quarters green "
          f"with {COUNT} positive posts.", flush=True)
    for name, c, a, p in picks:
        print(f"   {name:<24} {c:>4} posts @ avg {a:+.2f}  ->  +{p} positive", flush=True)
elif args.neutral_quarters > 0:
    plan, picks = build_neutral_plan(quarters, args.neutral_quarters, rng)
    if not plan:
        sys.exit("No non-neutral quarters with posts to neutralize.")
    COUNT = len(plan)
    sentiments = ["neutral"]
    print(f"Neutral-bias mode: pulling {len(picks)} quarters toward neutral "
          f"with {COUNT} neutral posts.", flush=True)
    for name, c, a, p in picks:
        print(f"   {name:<24} {c:>4} posts @ avg {a:+.2f}  ->  +{p} neutral", flush=True)
else:
    # Optional floor: raise the count so every quarter reaches at least
    # --min-per-quarter TOTAL posts (existing + new), filling deficits first.
    COUNT = args.count
    if args.min_per_quarter > 0:
        deficit = sum(max(0, args.min_per_quarter - (q.get("post_count") or 0)) for q in quarters)
        COUNT = max(args.count, deficit)
        if COUNT > args.count:
            print(f"--min-per-quarter {args.min_per_quarter}: raising count "
                  f"{args.count} -> {COUNT} to bring every quarter to the floor.", flush=True)
    plan = build_coverage_plan(quarters, COUNT, rng, ignore_existing=args.even)

# Verify the model is actually pulled BEFORE the (slow) street prefetch, so a
# wrong --model fails in ~2s instead of after fetching streets for 77 quarters.
client = OllamaClient()
if not client.is_available(args.model):
    print("MODEL NOT AVAILABLE:", args.model, "| have:", client.list_models())
    sys.exit(2)

# ---- Real-street grounding: fetch each planned quarter's ACTUAL streets ----
# from OpenStreetMap (cached to disk). The engine injects one of these (a
# boulevard, by preference) and verifies any street the model writes, so posts
# stop borrowing streets from the wrong side of the city. Fetched in parallel
# (Overpass is the bottleneck, not CPU) and cached, so it's a one-time cost.
streets_map = {}
if not args.no_streets:
    from synthetic import streets as streetlib
    cache = streetlib.load_cache()
    cmap = {q["name"]: (q.get("centroid_lat"), q.get("centroid_lng")) for q in quarters}
    plan_quarters = sorted({name for name, _ in plan})
    todo = []
    for qn in plan_quarters:
        if qn in cache:
            streets_map[qn] = cache[qn]      # already cached from a previous run
        else:
            todo.append(qn)
    print(f"Real streets: {len(plan_quarters) - len(todo)} cached, fetching {len(todo)} "
          f"from OSM (parallel) …", flush=True)

    def _fetch_streets(qn):
        lat, lon = cmap.get(qn, (None, None))
        if lat is None or lon is None:
            return qn, None
        try:
            return qn, streetlib.fetch_streets(float(lat), float(lon), radius=args.street_radius)
        except Exception:
            return qn, None

    workers = min(6, max(2, args.concurrency))
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as sx:
        for fut in as_completed([sx.submit(_fetch_streets, qn) for qn in todo]):
            qn, info = fut.result()
            streets_map[qn] = info
            if info and info.get("all"):
                cache[qn] = info
            done += 1
            if done % 5 == 0 or done == len(todo):
                have = sum(1 for v in streets_map.values() if v)
                sys.stdout.write(f"\r   fetched {done}/{len(todo)} - {have}/{len(plan_quarters)} "
                                 f"quarters have streets   ")
                sys.stdout.flush()
            if done % 15 == 0:                 # persist so Ctrl+C mid-prefetch keeps progress
                streetlib.save_cache(cache)
    streetlib.save_cache(cache)
    if todo:
        print(flush=True)

specs = sample_specs(
    COUNT, sources=["reddit", "x", "instagram", "facebook"],
    sentiments=sentiments,
    districts=[(q["name"], _sector_of(q.get("parent"))) for q in quarters],
    balance=args.balance, rng=rng)
# Override each spec's location with the coverage plan (decouples topic/
# sentiment mix from *where* the post is set) and attach its real streets.
# In --mixed mode the per-post sentiment comes from the plan, so re-roll the
# angle to match (angles are sentiment-specific).
for i, (s, (name, sector)) in enumerate(zip(specs, plan)):
    s.district_name = name
    s.sector = sector
    s.streets = streets_map.get(name)
    if plan_sents is not None:
        s.sentiment = plan_sents[i]
        s.angle = rng.choice(ANGLES.get(s.sentiment, ANGLES["neutral"]))

# --------------------------------------------------------------------------- engine + sink
# (client + model availability were checked above, before the street prefetch.)
engine = SyntheticEngine(client, args.model, max_revisions=args.max_revisions,
                         min_authenticity=3, language="English",
                         street_max_fix=0 if args.no_streets else args.street_fixes)

sink = None
if not args.no_insert:
    if not SERVICE:
        print("⚠  No service_role key (set SUPABASE_SERVICE_KEY in .env) - "
              "DB insert OFF; writing JSONL only.", flush=True)
    else:
        try:
            sink = DBSink(SERVICE, dmap)
        except Exception as exc:  # noqa: BLE001
            print(f"⚠  Service key/insert setup failed ({exc}) - DB insert OFF.", flush=True)
            sink = None

# --------------------------------------------------------------------------- run
out = pathlib.Path(args.out)
out.parent.mkdir(parents=True, exist_ok=True)
fh = out.open("w", encoding="utf-8")
buf = []
st = {"done": 0, "kept": 0, "accepted": 0, "inserted": 0, "errors": 0, "t0": time.time()}
covered = set()


def flush(force=False):
    global buf
    if sink and buf and (force or len(buf) >= args.insert_batch):
        batch, buf = buf, []
        st["inserted"] += sink.insert(batch)


def progress():
    d, total = st["done"], len(specs)
    el = time.time() - st["t0"]
    rate = d / el if el else 0
    eta = (total - d) / rate / 60 if rate else 0
    pct = d / total if total else 1
    fill = int(24 * pct)
    bar = "█" * fill + "░" * (24 - fill)
    return (f"\r[{bar}] {d}/{total} {pct*100:4.1f}% | ok {st['accepted']} "
            f"ins {st['inserted']} err {st['errors']} | {rate:4.1f}/s ETA {eta:4.1f}m   ")


print(f"Generating {len(specs)} posts | model={args.model} concurrency={args.concurrency} "
      f"max_revisions={args.max_revisions} | insert={'ON' if sink else 'OFF'}", flush=True)
_mode = ("mixed-scene" if args.mixed
         else "positive-bias" if args.positive_quarters > 0
         else "neutral-bias" if args.neutral_quarters > 0
         else "splitting evenly" if args.even else "filling emptiest first")
print(f"Quarters: {len(quarters)} total, {empty_before} empty - {_mode} -> {out}", flush=True)

ex = ThreadPoolExecutor(max_workers=max(1, args.concurrency))
futures = [ex.submit(engine.generate_one, s) for s in specs]
interrupted = False
try:
    for fut in as_completed(futures):
        p = fut.result()
        st["done"] += 1
        if p.error:
            st["errors"] += 1
        else:
            fh.write(json.dumps(p.to_record(), ensure_ascii=False) + "\n")
            fh.flush()
            st["kept"] += 1
            if p.accepted:
                st["accepted"] += 1
                covered.add(p.spec.district_name)
                if sink:
                    buf.append(p.to_record())
                    flush()
        sys.stdout.write(progress())
        sys.stdout.flush()
except KeyboardInterrupt:
    interrupted = True
    sys.stdout.write("\n⏹  Interrupted - cancelling pending posts and flushing…\n")
    sys.stdout.flush()
finally:
    ex.shutdown(wait=False, cancel_futures=True)
    flush(force=True)
    fh.close()

# --------------------------------------------------------------------------- summary
el = time.time() - st["t0"]
print()
print("─" * 64)
print(f"{'INTERRUPTED' if interrupted else 'DONE'} in {el/60:.1f} min  ({st['done']}/{len(specs)} attempted)")
print(f"  written   : {st['kept']} posts -> {out}   ({st['errors']} generation errors)")
acc_pct = st["accepted"] / max(st["kept"], 1) * 100
print(f"  accepted  : {st['accepted']}  ({acc_pct:.0f}% of written)")
if sink:
    print(f"  inserted  : {st['inserted']} into Supabase")
    print(f"  quarters touched this run: {len(covered)}")
    try:
        after = fetch_quarters(SERVICE or READ_KEY)
        empty_after = sum(1 for q in after if not (q.get("post_count") or 0))
        print(f"  empty quarters: {empty_before} -> {empty_after}")
    except Exception:  # noqa: BLE001
        pass
else:
    print("  insert    : OFF - to insert later, run:")
    print(f"              python scripts/insert_synthetic.py {out}")
