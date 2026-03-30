"""Tests for ml/firm_database.py."""

from __future__ import annotations

import pytest

from legal_format_engine.ml.firm_database import FirmDatabase, FirmRecord, _jaccard, _tokenize


@pytest.fixture(scope="module")
def db():
    return FirmDatabase()


class TestFirmDatabase:
    def test_total_count(self, db):
        assert db.total_count >= 160

    def test_exact_lookup(self, db):
        result = db.lookup("Kirkland & Ellis LLP")
        assert result is not None
        assert result.canonical_name == "Kirkland & Ellis LLP"

    def test_exact_lookup_case_insensitive(self, db):
        result = db.lookup("kirkland & ellis llp")
        assert result is not None
        assert result.canonical_name == "Kirkland & Ellis LLP"

    def test_fuzzy_lookup_and_to_ampersand(self, db):
        result = db.lookup("KIRKLAND AND ELLIS")
        assert result is not None
        assert result.canonical_name == "Kirkland & Ellis LLP"

    def test_fuzzy_lookup_partial_name(self, db):
        result = db.lookup("Latham Watkins")
        assert result is not None
        assert "Latham" in result.canonical_name

    def test_fuzzy_lookup_skadden(self, db):
        result = db.lookup("Skadden Arps Slate Meagher Flom")
        assert result is not None
        assert "Skadden" in result.canonical_name

    def test_fuzzy_lookup_skadden_low_threshold(self, db):
        result = db.lookup("Skadden Arps", threshold=0.3)
        assert result is not None
        assert "Skadden" in result.canonical_name

    def test_lookup_jones_day(self, db):
        result = db.lookup("Jones Day")
        assert result is not None
        assert result.canonical_name == "Jones Day"

    def test_lookup_no_match(self, db):
        result = db.lookup("Totally Fake Law Firm That Does Not Exist")
        assert result is None

    def test_lookup_empty(self, db):
        result = db.lookup("")
        assert result is None

    def test_lookup_threshold(self, db):
        # Very high threshold should reject fuzzy matches
        result = db.lookup("Kirkland", threshold=0.99)
        assert result is None  # "Kirkland" alone doesn't match at 0.99

    def test_am_law_category(self, db):
        firms = db.get_by_category("am_law")
        assert len(firms) == 50

    def test_am_law_ranked(self, db):
        firms = db.get_by_category("am_law")
        ranked = [f for f in firms if f.rank is not None]
        assert len(ranked) == 50
        assert ranked[0].rank == 1

    def test_wisconsin_category(self, db):
        firms = db.get_by_category("wisconsin")
        assert len(firms) >= 10
        names = [f.canonical_name for f in firms]
        assert "Foley & Lardner LLP" in names
        assert "Quarles & Brady LLP" in names

    def test_state_ag_category(self, db):
        firms = db.get_by_category("state_ag")
        assert len(firms) == 50  # all 50 states

    def test_state_pd_category(self, db):
        firms = db.get_by_category("state_pd")
        assert len(firms) == 50

    def test_federal_category(self, db):
        firms = db.get_by_category("federal")
        assert len(firms) >= 3

    def test_legal_aid_category(self, db):
        firms = db.get_by_category("legal_aid")
        assert len(firms) >= 10

    def test_appellate_category(self, db):
        firms = db.get_by_category("appellate")
        assert len(firms) >= 5

    def test_search(self, db):
        results = db.search("Kirkland")
        assert len(results) >= 1
        assert any("Kirkland" in f.canonical_name for f in results)

    def test_search_case_insensitive(self, db):
        results = db.search("kirkland")
        assert len(results) >= 1

    def test_search_limit(self, db):
        results = db.search("Law", limit=3)
        assert len(results) <= 3

    def test_search_no_results(self, db):
        results = db.search("xyzzynotafirm")
        assert len(results) == 0

    def test_wisconsin_ag(self, db):
        result = db.lookup("Wisconsin Attorney General's Office")
        assert result is not None
        assert result.category == "state_ag"

    def test_doj_lookup(self, db):
        result = db.lookup("United States Department of Justice")
        assert result is not None
        assert result.category == "federal"

    def test_aclu_lookup(self, db):
        result = db.lookup("American Civil Liberties Union (ACLU)")
        assert result is not None
        assert result.category == "legal_aid"

    def test_foley_lardner(self, db):
        result = db.lookup("Foley & Lardner")
        assert result is not None
        assert result.canonical_name == "Foley & Lardner LLP"

    def test_michael_best(self, db):
        result = db.lookup("Michael Best & Friedrich")
        assert result is not None

    def test_reinhart(self, db):
        result = db.lookup("Reinhart Boerner Van Deuren")
        assert result is not None


class TestTokenize:
    def test_basic(self):
        tokens = _tokenize("Kirkland & Ellis LLP")
        assert "kirkland" in tokens
        assert "ellis" in tokens
        assert "llp" not in tokens  # stripped

    def test_removes_common(self):
        tokens = _tokenize("The Firm of and")
        assert "the" not in tokens
        assert "of" not in tokens
        assert "and" not in tokens
        assert "firm" in tokens

    def test_removes_punctuation(self):
        tokens = _tokenize("Skadden, Arps, Slate")
        assert "skadden" in tokens
        assert "arps" in tokens


class TestJaccard:
    def test_identical(self):
        s = {"a", "b", "c"}
        assert _jaccard(s, s) == 1.0

    def test_disjoint(self):
        assert _jaccard({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        assert _jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)

    def test_empty(self):
        assert _jaccard(set(), {"a"}) == 0.0
        assert _jaccard(set(), set()) == 0.0


class TestFirmRecord:
    def test_defaults(self):
        fr = FirmRecord(canonical_name="Test", category="am_law")
        assert fr.aliases == []
        assert fr.rank is None

    def test_post_init(self):
        fr = FirmRecord(canonical_name="X", category="x")
        assert fr.aliases is not None
