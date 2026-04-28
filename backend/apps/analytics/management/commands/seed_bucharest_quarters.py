"""Seed the District table with the canonical Bucharest hierarchy.

Creates one ``city`` row (București), six ``sector`` rows
(Sector 1–6), and ~83 ``quarter`` rows (Aviației, Băneasa, Crângași,
Drumul Taberei, …) drawn from
``apps.analytics.bucharest_quarters.BUCHAREST_QUARTERS``.

Coordinates are pulled from OpenStreetMap via the Overpass API in a
single batch query — every element tagged ``place=neighbourhood`` /
``place=quarter`` / ``place=suburb`` inside the Bucharest admin area.
Names are matched diacritic-insensitively against the canonical list.
Quarters not found in OSM are still created without coordinates so
the LLM-driven assignment still has somewhere to write to.

Idempotent — re-running only fills in missing fields, never wipes
existing post links.
"""

from __future__ import annotations

import logging
import unicodedata

from django.core.management.base import BaseCommand

from apps.analytics.bucharest_quarters import BUCHAREST_QUARTERS, _strip_diacritics
from apps.analytics.models import District


logger = logging.getLogger(__name__)


# Hand-picked centroid fallbacks for quarters that OSM doesn't model as
# a `place=*` element (some are landmarks rather than neighborhoods).
# Lat/lng pairs are rough centroids — accurate to a few hundred meters.
FALLBACK_CENTROIDS: dict[str, tuple[float, float]] = {
    "Calea Victoriei": (44.4395, 26.0966),
    "Calea Călărașilor": (44.4329, 26.1208),
    "Calea Moșilor": (44.4452, 26.1098),
    "Calea Griviței": (44.4567, 26.0760),
    "Magheru": (44.4427, 26.1004),
    "Cișmigiu": (44.4356, 26.0917),
    "Centrul Civic": (44.4296, 26.1027),
    "Piața Iancului": (44.4509, 26.1248),
    "Piața Romană": (44.4477, 26.0975),
    "Piața Universității": (44.4361, 26.1010),
    "Strădun": (44.4290, 26.0190),
    "Politehnica": (44.4380, 26.0510),
    "Plevnei": (44.4408, 26.0747),
    "Drumul Sării": (44.4221, 26.0552),
    "Eroii Revoluției": (44.4046, 26.1071),
    "Apărătorii Patriei": (44.3795, 26.1402),
    "Brâncoveanu": (44.3950, 26.1310),
    "Progresul": (44.3760, 26.0831),
    "Nerva Traian": (44.4300, 26.1165),
    "Decebal": (44.4318, 26.1235),
    "Antiaeriană": (44.4080, 26.0700),
    "Pieptănari": (44.4022, 26.0820),
    "Ghencea Vest": (44.4140, 26.0290),
    "Giulești-Sârbi": (44.4655, 26.0240),
    "Chibrit": (44.4640, 26.0760),
    "Bucureștii Noi": (44.4860, 26.0530),
    # Sister entries for quarters whose OSM neighbourhood node is named
    # differently (e.g. OSM has "Piața Romană" but our list also has "Romană").
    "Romană": (44.4477, 26.0975),
    "Victoriei": (44.4528, 26.0866),
    "Unirii": (44.4267, 26.1025),
    "Balta Albă": (44.4192, 26.1564),
    "Muncii": (44.4310, 26.1335),
    "Nicolae Grigorescu": (44.4188, 26.1493),
    "Theodor Pallady": (44.4106, 26.1909),
    "Titan": (44.4170, 26.1567),
    "Olteniței": (44.3768, 26.1379),
    "Sebastian": (44.4135, 26.0762),
}


class Command(BaseCommand):
    help = "Seed the District table with Bucharest sectors + quarters (one OSM call)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-osm",
            action="store_true",
            help="Don't call Overpass — use only the hardcoded fallback centroids.",
        )

    # Approximate centroids — used so the city + sector layers also
    # render on the map without needing OSM polygons for them.
    CITY_CENTROID = (44.4378, 26.0969)
    SECTOR_CENTROIDS = {
        1: (44.4900, 26.0700),
        2: (44.4500, 26.1200),
        3: (44.4200, 26.1500),
        4: (44.3900, 26.1100),
        5: (44.4150, 26.0500),
        6: (44.4350, 26.0300),
    }

    def handle(self, *args, **opts):
        # 1. City + 6 sectors first (parents must exist before children).
        city_district = self._upsert(
            name="București", kind="city", parent=None,
            centroid=self.CITY_CENTROID,
        )
        sector_districts: dict[int, District] = {}
        for n in range(1, 7):
            sector_districts[n] = self._upsert(
                name=f"Sector {n}", kind="sector", parent=city_district,
                centroid=self.SECTOR_CENTROIDS.get(n),
            )

        # 2. Pull all neighborhood-like nodes in Bucharest in one call.
        osm_lookup: dict[str, tuple[float, float]] = {}
        if not opts["skip_osm"]:
            osm_lookup = self._fetch_overpass_centroids()
            self.stdout.write(
                f"OSM returned {len(osm_lookup)} neighborhood centroids."
            )
        else:
            self.stdout.write(self.style.WARNING("Skipping OSM (--skip-osm)."))

        # 3. Quarters.
        created_q = 0
        with_coords = 0
        for name, sector_n in BUCHAREST_QUARTERS:
            district, was_created = District.objects.get_or_create(
                name=name,
                defaults={
                    "city": "București",
                    "kind": "quarter",
                    "parent": sector_districts.get(sector_n),
                },
            )
            if was_created:
                created_q += 1

            # Backfill missing parent/kind on previously-created rows.
            dirty = []
            if district.kind != "quarter":
                district.kind = "quarter"
                dirty.append("kind")
            if district.parent_id != sector_districts.get(sector_n).id:
                district.parent = sector_districts.get(sector_n)
                dirty.append("parent")

            # Coordinates: OSM > fallback table > nothing.
            coords = osm_lookup.get(_normalize_key(name)) or FALLBACK_CENTROIDS.get(name)
            if coords and not district.centroid_lat:
                district.centroid_lat, district.centroid_lng = coords
                dirty.extend(["centroid_lat", "centroid_lng"])

            if district.centroid_lat is not None:
                with_coords += 1

            if dirty:
                district.save(update_fields=dirty)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {District.objects.filter(kind='quarter').count()} quarters "
                f"({created_q} new), {with_coords} with coordinates, "
                f"6 sectors, 1 city."
            )
        )

    # ------------------------------------------------------------------ helpers

    def _upsert(self, *, name: str, kind: str, parent, centroid=None) -> District:
        obj, created = District.objects.get_or_create(
            name=name,
            defaults={"city": "București", "kind": kind, "parent": parent},
        )
        # Make sure kind/parent reflect the canonical hierarchy on existing rows.
        dirty = []
        if obj.kind != kind:
            obj.kind = kind
            dirty.append("kind")
        if (parent and obj.parent_id != parent.id) or (parent is None and obj.parent_id):
            obj.parent = parent
            dirty.append("parent")
        if centroid and obj.centroid_lat is None:
            obj.centroid_lat, obj.centroid_lng = centroid
            dirty.extend(["centroid_lat", "centroid_lng"])
        if dirty:
            obj.save(update_fields=dirty)
        return obj

    def _fetch_overpass_centroids(self) -> dict[str, tuple[float, float]]:
        """One batched Overpass call → ``{normalized_name: (lat, lng)}``."""
        try:
            from geo.overpass import OverpassClient
        except ImportError:
            self.stderr.write(self.style.WARNING(
                "geo.overpass not importable — falling back to FALLBACK_CENTROIDS only."
            ))
            return {}

        # Bucharest bounding box (south, west, north, east).
        # `area["name"="București"]` is unreliable in the public Overpass
        # mirror, so we filter geographically — Bucharest is small enough
        # that the bbox doesn't pick up surrounding county neighborhoods.
        bbox = "44.35,25.95,44.55,26.20"
        query = (
            "[out:json][timeout:90];\n"
            "(\n"
            f'  node["place"~"^(quarter|neighbourhood|suburb)$"]({bbox});\n'
            f'  way["place"~"^(quarter|neighbourhood|suburb)$"]({bbox});\n'
            f'  relation["place"~"^(quarter|neighbourhood|suburb)$"]({bbox});\n'
            ");\n"
            "out center tags;"
        )

        client = OverpassClient(timeout=90)
        self.stdout.write("Querying Overpass API (one batched call)…")
        result = client.query(query)
        if not result:
            self.stderr.write(self.style.WARNING("Overpass call failed."))
            return {}

        out: dict[str, tuple[float, float]] = {}
        for el in result.get("elements", []):
            tags = el.get("tags") or {}
            name = tags.get("name") or tags.get("name:ro") or ""
            if not name:
                continue
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lng = el.get("lon") or (el.get("center") or {}).get("lon")
            if lat is None or lng is None:
                continue
            out[_normalize_key(name)] = (float(lat), float(lng))
        return out


def _normalize_key(name: str) -> str:
    """Lowercase, strip diacritics & punctuation → single key for lookup."""
    s = _strip_diacritics(name.lower())
    return "".join(ch for ch in s if ch.isalnum() or ch.isspace()).strip()
