"""Insert generated posts into Supabase via PostgREST (anon key).

Reads a JSONL file of generated records, resolves district ids + topic
categories, inserts prelabeled analytics_socialpost rows (so the `feedbacks`
view renders them), then links each post to its topic. Batched for large runs.

Usage:
    python scripts/insert_synthetic.py <ANON_KEY>                       # uses data/synthetic/demo.jsonl
    python scripts/insert_synthetic.py <ANON_KEY> data/synthetic/run10k.jsonl
"""
import os, sys, json, random, pathlib
from datetime import datetime, timezone, timedelta
import requests

URL = "https://ujdkiorhdynsrlkhrtcm.supabase.co"
ROOT = pathlib.Path(__file__).resolve().parent.parent


def _env_value(path, key):
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith(key + "=") and s.split("=", 1)[1].strip():
            return s.split("=", 1)[1].strip()
    return None


def _anon_key():
    """Write key: prefer the service_role key (bypasses RLS) from
    $SUPABASE_SERVICE_KEY or the root .env; fall back to the anon key (which
    is RLS-blocked for writes unless RLS is lifted)."""
    return (
        os.environ.get("SUPABASE_SERVICE_KEY")
        or _env_value(ROOT / ".env", "SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or _env_value(ROOT / "frontend-react" / ".env", "VITE_SUPABASE_ANON_KEY")
        or _raise_no_key()
    )


def _raise_no_key():
    raise SystemExit("No Supabase key (set SUPABASE_SERVICE_KEY in .env, or SUPABASE_ANON_KEY).")


KEY = _anon_key()
INFILE = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "synthetic" / "demo.jsonl"
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
BATCH = 500
SPREAD_DAYS = 60  # scatter original_date across the last N days for a realistic feed


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


recs = [json.loads(l) for l in INFILE.read_text(encoding="utf-8").splitlines() if l.strip()]
recs = [r for r in recs if r.get("text")]
print(f"loaded {len(recs)} records from {INFILE}")

dz = requests.get(f"{URL}/rest/v1/analytics_district?select=id,name", headers=H); dz.raise_for_status()
_districts = dz.json()
dmap = {d["name"]: d["id"] for d in _districts}


def _norm(s):
    """Diacritic-insensitive key. Supabase district names were seeded
    without Romanian diacritics ('Herastrau'), but generated posts use the
    canonical spelling ('Herăstrău'); fall back to a normalized match."""
    s = (s or "").lower()
    for a, b in (("ș", "s"), ("ş", "s"), ("ț", "t"), ("ţ", "t"),
                 ("ă", "a"), ("â", "a"), ("î", "i")):
        s = s.replace(a, b)
    return s.strip()


dmap_norm = {_norm(d["name"]): d["id"] for d in _districts}

cats = ["infrastructure", "cleanliness", "safety", "transport", "greenspace", "other"]
requests.post(f"{URL}/rest/v1/analytics_topiccategory?on_conflict=name",
              headers={**H, "Prefer": "resolution=ignore-duplicates,return=minimal"},
              data=json.dumps([{"name": c, "description": ""} for c in cats]))
tc = requests.get(f"{URL}/rest/v1/analytics_topiccategory?select=id,name", headers=H); tc.raise_for_status()
tmap = {t["name"]: t["id"] for t in tc.json()}

SENT_SCORE = {"negative": -0.85, "positive": 0.85, "neutral": 0.0}
SENT_LABEL = {"negative": "Negative", "positive": "Positive", "neutral": "Neutral"}
rng = random.Random(7)
now = datetime.now(timezone.utc)
rows = []
for r in recs:
    sent = r["sentiment"]
    od = (now - timedelta(minutes=rng.randint(5, SPREAD_DAYS * 24 * 60))).isoformat()
    rows.append({
        "source": r["source"], "source_id": r["id"], "content": r["text"],
        "author": (r.get("author") or "")[:255], "url": "", "location_name": r["district"],
        "district_id": dmap.get(r["district"]) or dmap_norm.get(_norm(r["district"])),
        "sentiment_score": SENT_SCORE.get(sent, 0.0), "sentiment_label": SENT_LABEL.get(sent, "Neutral"),
        "topic_scores": {r["app_topic"]: 1.0},
        "score": max(int(r.get("authenticity") or 1), 1) * rng.randint(3, 30),
        "extra_data": {"synthetic": {k: r.get(k) for k in
                       ("subtopic", "app_topic", "sentiment", "angle", "authenticity", "accepted", "hashtags")}},
        "language": "en", "ingestion_method": "synthetic",
        "original_date": od, "scraped_at": now.isoformat(), "processed_at": now.isoformat(),
    })

app_by_sid = {r["id"]: r["app_topic"] for r in recs}
total_new = 0
for bi, batch in enumerate(chunks(rows, BATCH), 1):
    resp = requests.post(
        f"{URL}/rest/v1/analytics_socialpost?on_conflict=source,source_id",
        headers={**H, "Prefer": "resolution=ignore-duplicates,return=representation"},
        data=json.dumps(batch))
    if resp.status_code >= 300:
        print("INSERT error:", resp.status_code, resp.text[:400]); sys.exit(1)
    inserted = resp.json()
    total_new += len(inserted)
    links = [{"socialpost_id": row["id"], "topiccategory_id": tmap[app_by_sid[row["source_id"]]]}
             for row in inserted if app_by_sid.get(row["source_id"]) in tmap]
    for lb in chunks(links, 1000):
        requests.post(
            f"{URL}/rest/v1/analytics_socialpost_topics?on_conflict=socialpost_id,topiccategory_id",
            headers={**H, "Prefer": "resolution=ignore-duplicates,return=minimal"}, data=json.dumps(lb))
    print(f"batch {bi}: +{len(inserted)} posts (running total {total_new})", flush=True)

print(f"DONE: inserted {total_new} new posts from {len(rows)} records.")
