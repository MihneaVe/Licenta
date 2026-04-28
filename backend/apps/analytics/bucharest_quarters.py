"""Canonical list of Bucharest quarters (cartiere).

Compiled from the Romanian Wikipedia entry "Cartierele Bucureștiului"
and cross-checked against OpenStreetMap. Each entry is
``(quarter_name, parent_sector_number)``. Aliases that the LLM /
regex layer may surface in raw text are handled in
:data:`QUARTER_ALIASES` below.

The list is the source of truth for seeding. Coordinates and (when
available) boundary polygons are fetched from Overpass and merged in
by the ``seed_bucharest_quarters`` management command.
"""

from __future__ import annotations


# (name, sector) — kept stable so external tooling can rely on this list.
BUCHAREST_QUARTERS: list[tuple[str, int]] = [
    # ---- Sector 1 ----
    ("Aviației", 1),
    ("Aviatorilor", 1),
    ("Băneasa", 1),
    ("Bucureștii Noi", 1),
    ("Chibrit", 1),
    ("Chitila", 1),
    ("Damaroaia", 1),
    ("Domenii", 1),
    ("Dorobanți", 1),
    ("Floreasca", 1),
    ("Gara de Nord", 1),
    ("Grivița", 1),
    ("Herăstrău", 1),
    ("Pajura", 1),
    ("Pipera", 1),
    ("Primăverii", 1),
    ("Romană", 1),
    ("Victoriei", 1),

    # ---- Sector 2 ----
    ("Andronache", 2),
    ("Baicului", 2),
    ("Colentina", 2),
    ("Doamna Ghica", 2),
    ("Fundeni", 2),
    ("Iancului", 2),
    ("Moșilor", 2),
    ("Obor", 2),
    ("Pantelimon", 2),
    ("Plumbuita", 2),
    ("Ștefan cel Mare", 2),
    ("Tei", 2),
    ("Vatra Luminoasă", 2),

    # ---- Sector 3 ----
    ("Balta Albă", 3),
    ("Centrul Civic", 3),
    ("Dristor", 3),
    ("Dudești", 3),
    ("Lipscani", 3),
    ("Muncii", 3),
    ("Nicolae Grigorescu", 3),
    ("Theodor Pallady", 3),
    ("Titan", 3),
    ("Unirii", 3),
    ("Vitan", 3),

    # ---- Sector 4 ----
    ("Berceni", 4),
    ("Giurgiului", 4),
    ("Olteniței", 4),
    ("Tineretului", 4),
    ("Văcărești", 4),

    # ---- Sector 5 ----
    ("13 Septembrie", 5),
    ("Antiaeriană", 5),
    ("Cotroceni", 5),
    ("Dealul Spirii", 5),
    ("Ferentari", 5),
    ("Ghencea", 5),
    ("Pieptănari", 5),
    ("Rahova", 5),
    ("Sebastian", 5),

    # ---- Sector 6 ----
    ("Crângași", 6),
    ("Drumul Taberei", 6),
    ("Ghencea Vest", 6),
    ("Giulești", 6),
    ("Giulești-Sârbi", 6),
    ("Grozăvești", 6),
    ("Militari", 6),
    ("Plevnei", 6),
    ("Politehnica", 6),
    ("Regie", 6),
    ("Strădun", 6),

    # ---- Cross-sector / bordering / commonly mentioned ----
    ("Drumul Sării", 6),
    ("Apărătorii Patriei", 4),
    ("Brâncoveanu", 4),
    ("Eroii Revoluției", 4),
    ("Progresul", 4),
    ("Nerva Traian", 3),
    ("Decebal", 3),
    ("Piața Iancului", 2),
    ("Piața Romană", 1),
    ("Piața Universității", 1),
    ("Magheru", 1),
    ("Cișmigiu", 1),
    ("Calea Victoriei", 1),
    ("Calea Călărașilor", 3),
    ("Calea Moșilor", 2),
    ("Calea Griviței", 1),
]


# Aliases / spelling variants the LLM and regex layers may see in the
# wild but which should map to the canonical name above.
QUARTER_ALIASES: dict[str, str] = {
    "drumul taberii": "Drumul Taberei",
    "dr taberei": "Drumul Taberei",
    "dr. taberei": "Drumul Taberei",
    "drumul-taberei": "Drumul Taberei",
    "stefan cel mare": "Ștefan cel Mare",
    "ștefan-cel-mare": "Ștefan cel Mare",
    "valea cascadelor": "Militari",
    "iuliu maniu": "Militari",
    "berceni sud": "Berceni",
    "vacaresti": "Văcărești",
    "centrul vechi": "Lipscani",
    "old town": "Lipscani",
    "victoria sq": "Victoriei",
    "piata victoriei": "Victoriei",
    "unirii sq": "Unirii",
    "piata unirii": "Unirii",
}


CANONICAL_NAMES = [name for name, _ in BUCHAREST_QUARTERS]


def normalize_quarter_name(raw: str) -> str | None:
    """Map a free-form mention back to a canonical quarter name.

    Returns ``None`` when no canonical match is found. Comparison is
    case-insensitive and strips Romanian diacritics for the lookup so
    "Drumul Taberii" / "Drumul Taberei" / "drumul-taberei" all converge.
    """
    if not raw:
        return None
    key = _strip_diacritics(raw.lower().strip())

    # Direct alias hit.
    aliased = QUARTER_ALIASES.get(key)
    if aliased:
        return aliased

    # Canonical match (case + diacritic insensitive).
    for canonical in CANONICAL_NAMES:
        if _strip_diacritics(canonical.lower()) == key:
            return canonical

    return None


def _strip_diacritics(text: str) -> str:
    table = str.maketrans({
        "ă": "a", "â": "a", "Ă": "a", "Â": "a",
        "î": "i", "Î": "i",
        "ș": "s", "Ș": "s", "ş": "s", "Ş": "s",
        "ț": "t", "Ț": "t", "ţ": "t", "Ţ": "t",
    })
    return text.translate(table)
