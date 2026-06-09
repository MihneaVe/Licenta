"""Unit tests for scripts.process_posts.DistrictResolver — fake session, no DB."""

from types import SimpleNamespace

from scripts.process_posts import DistrictResolver, _norm


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeSession:
    def __init__(self, districts):
        self._districts = districts

    def scalars(self, _stmt):
        return _FakeResult(self._districts)


def _make_resolver():
    districts = [
        SimpleNamespace(id=1, name="București", kind="city"),
        SimpleNamespace(id=2, name="Sector 3", kind="sector"),
        SimpleNamespace(id=3, name="Grozăvești", kind="quarter"),
        SimpleNamespace(id=4, name="Tei", kind="quarter"),
        SimpleNamespace(id=5, name="Tei Toboc", kind="quarter"),
    ]
    return DistrictResolver(_FakeSession(districts))


def test_norm_folds_romanian_diacritics():
    assert _norm("Grozăvești") == "grozavesti"
    assert _norm("Ţară şi Ţânţar") == "tara si tantar"  # legacy cedilla forms too


def test_quarter_match_is_diacritic_insensitive():
    r = _make_resolver()
    assert r.resolve("S-a spart o teava in grozavesti azi").name == "Grozăvești"


def test_longest_quarter_name_wins():
    r = _make_resolver()
    assert r.resolve("mizerie in tei toboc langa lac").name == "Tei Toboc"


def test_quarter_word_boundary():
    r = _make_resolver()
    # 'tei' inside 'teiul' must not match → falls through to the city default
    assert r.resolve("pe strada teiul doamnei e blocaj").name == "București"


def test_sector_fallback():
    r = _make_resolver()
    assert r.resolve("gropi mari in sectorul 3").name == "Sector 3"


def test_city_default_when_nothing_matches():
    r = _make_resolver()
    assert r.resolve("nimic concret aici").name == "București"


def test_quarter_beats_sector_when_both_present():
    r = _make_resolver()
    assert r.resolve("in Tei, sector 2, e galagie").name == "Tei"
