"""Real street names per Bucharest quarter, from OpenStreetMap (Overpass).

Used to keep synthetic posts factually grounded: instead of inventing or
borrowing a street from the wrong side of the city, a post that references a
street uses a *real* street that actually exists near that quarter, with a
preference for the main arteries (Bulevardul / Calea / Șoseaua / primary roads).

Fetches are cached to data/synthetic/streets_cache.json so the Overpass calls
happen once per quarter.
"""

from __future__ import annotations

import json
import pathlib
import re
import time

import requests

_OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
_UA = {"User-Agent": "civicpulse-thesis/1.0 (synthetic demo street grounding)"}

# OSM highway classes that read as major arteries (boulevards / calea / șosea).
_MAJOR_HIGHWAY = {"motorway", "trunk", "primary", "secondary"}
# Romanian street-type prefixes that denote a big road by name.
_MAJOR_NAME_RE = re.compile(r"^(Bulevardul|Bulevard|Calea|Șoseaua|Soseaua|Splaiul)\b", re.IGNORECASE)

# Street-type prefixes we verify (streets — not squares/parks/landmarks, which
# may legitimately be named even if they're not in the street list).
_STREET_RE = re.compile(
    r"\b(?:Strada|Str\.?|Bulevardul|Bulevard|Bd\.?|B-dul|Calea|Șoseaua|Soseaua|"
    r"Aleea|Splaiul|Drumul|Intrarea|Prelungirea)\s+"
    r"([A-ZĂÂÎȘȚ][\wĂÂÎȘȚăâîșț.\- ]{1,40}?)"
    r"(?=[\s]*(?:[.,;:!?\n)]|#|@|$|\bși\b|\bla\b|\bdin\b|\bcu\b))",
    re.UNICODE,
)

_CACHE_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "synthetic" / "streets_cache.json"


# --------------------------------------------------------------------------- fetch
def _overpass(lat: float, lon: float, radius: int) -> list[dict]:
    query = (f'[out:json][timeout:60];'
             f'way["highway"]["name"](around:{radius},{lat},{lon});out tags;')
    last_err = None
    for ep in _OVERPASS_ENDPOINTS:
        for attempt in range(3):
            try:
                r = requests.post(ep, data={"data": query}, headers=_UA, timeout=90)
                if r.status_code == 200 and "json" in r.headers.get("content-type", ""):
                    return r.json().get("elements", [])
                if r.status_code in (429, 504):  # rate-limited / gateway timeout
                    wait = int(r.headers.get("Retry-After", 0) or 0) or (2 * (attempt + 1))
                    time.sleep(min(wait, 12))
                    continue
                last_err = f"{ep} -> HTTP {r.status_code}"
            except Exception as exc:  # noqa: BLE001
                last_err = f"{ep} -> {exc}"
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Overpass failed: {last_err}")


def fetch_streets(lat: float, lon: float, radius: int = 1300, keep: int = 25) -> dict:
    """Return {"major": [...], "all": [...]} of real street names near (lat, lon).

    `major` is the boulevards/main roads (preferred when injecting); `all` is the
    full deduped list capped at `keep`, used to validate what the model writes.
    """
    elements = _overpass(lat, lon, radius)
    rank: dict[str, int] = {}
    for el in elements:
        tags = el.get("tags", {})
        name = (tags.get("name") or "").strip()
        if not name or len(name) < 3:
            continue
        hw = tags.get("highway", "")
        is_major = hw in _MAJOR_HIGHWAY or bool(_MAJOR_NAME_RE.match(name))
        r = 0 if is_major else 1
        rank[name] = min(rank.get(name, 2), r)

    ordered = sorted(rank.items(), key=lambda kv: (kv[1], kv[0]))
    major = [n for n, r in ordered if r == 0]
    alln = [n for n, _ in ordered][:keep]
    # make sure some majors survive the cap
    for m in major[:8]:
        if m not in alln:
            alln.append(m)
    return {"major": major[:15], "all": sorted(set(alln))}


# --------------------------------------------------------------------------- cache
def load_cache() -> dict:
    if _CACHE_PATH.exists():
        try:
            return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")


def streets_for(name: str, lat, lon, cache: dict, radius: int = 1300) -> dict | None:
    """Cached street lookup for a quarter. Returns None if geo/fetch unavailable."""
    if name in cache:
        return cache[name]
    if lat is None or lon is None:
        return None
    try:
        info = fetch_streets(float(lat), float(lon), radius=radius)
    except Exception:
        return None
    if not info["all"]:
        return None
    cache[name] = info
    return info


# --------------------------------------------------------------------------- pick / verify
def pick_street(info: dict | None, rng, major_bias: float = 0.7) -> str | None:
    """Choose one real street, preferring boulevards/main roads."""
    if not info or not info.get("all"):
        return None
    major, alln = info.get("major") or [], info["all"]
    if major and (not [s for s in alln if s not in major] or rng.random() < major_bias):
        return rng.choice(major)
    return rng.choice(alln)


def extract_streets(text: str) -> list[str]:
    """Return the street phrases (type prefix + name) referenced in `text`."""
    out = []
    for m in _STREET_RE.finditer(text or ""):
        out.append(m.group(0).strip(" .,"))
    return out


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip(" .,")


def validate(text: str, info: dict | None) -> list[str]:
    """Return street phrases in `text` that are NOT real streets for this quarter."""
    if not info or not info.get("all"):
        return []
    allowed = [_norm(s) for s in info["all"]]
    bad = []
    for phrase in extract_streets(text):
        p = _norm(phrase)
        # valid if it shares its core with any real street (either direction).
        if any(a in p or p in a or a.split()[-1] == p.split()[-1] for a in allowed if a):
            continue
        bad.append(phrase)
    return bad


def enforce(text: str, bad: list[str], chosen: str | None) -> str:
    """Deterministic safety net: replace hallucinated streets with `chosen`
    (or drop the type+name if we have no replacement)."""
    for phrase in bad:
        if chosen:
            text = text.replace(phrase, chosen)
        else:
            text = re.sub(re.escape(phrase) + r"\s*", "", text)
    return re.sub(r"\s{2,}", " ", text).strip()
