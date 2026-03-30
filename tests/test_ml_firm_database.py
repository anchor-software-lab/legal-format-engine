"""Tests for the firm database module."""

from __future__ import annotations

import pytest

from legal_format_engine.ml.firm_database import FirmDatabase, FirmRecord


@pytest.fixture
def db():
    return FirmDatabase()


class TestFirmDatabaseLookup:
    """Test exact and alias-based lookups."""

    def test_lookup_canonical_name(self, db):
        record = db.lookup("Kirkland & Ellis")
        assert record is not None
        assert record.canonical_name == "Kirkland & Ellis"
        assert record.am_law_rank == 1

    def test_lookup_alias(self, db):
        record = db.lookup("Kirkland & Ellis LLP")
        assert record is not None
        assert record.canonical_name == "Kirkland & Ellis"

    def test_lookup_short_alias(self, db):
        record = db.lookup("Skadden")
        assert record is not None
        assert "Skadden" in record.canonical_name

    def test_lookup_case_insensitive(self, db):
        record = db.lookup("kirkland & ellis")
        assert record is not None
        assert record.canonical_name == "Kirkland & Ellis"

    def test_lookup_not_found(self, db):
        assert db.lookup("Nonexistent Firm XYZ") is None

    def test_lookup_strips_entity_suffix(self, db):
        """Looking up a name with/without LLP should match the same firm."""
        with_llp = db.lookup("Latham & Watkins LLP")
        without_llp = db.lookup("Latham & Watkins")
        assert with_llp is not None
        assert without_llp is not None
        assert with_llp.canonical_name == without_llp.canonical_name


class TestFirmDatabaseNormalizeName:
    """Test firm name normalization."""

    def test_normalize_known_firm(self, db):
        assert db.normalize_name("Kirkland") == "Kirkland & Ellis"

    def test_normalize_alias_variant(self, db):
        assert db.normalize_name("K&E") == "Kirkland & Ellis"

    def test_normalize_unknown_firm_passthrough(self, db):
        assert db.normalize_name("Smith & Jones") == "Smith & Jones"

    def test_normalize_government(self, db):
        result = db.normalize_name("DOJ")
        assert result == "United States Department of Justice"

    def test_normalize_solicitor_general(self, db):
        result = db.normalize_name("Solicitor General")
        assert result == "Office of the Solicitor General"


class TestFirmDatabaseSearch:
    """Test search functionality."""

    def test_search_partial_name(self, db):
        results = db.search("Kirkland")
        assert len(results) >= 1
        assert any(r.canonical_name == "Kirkland & Ellis" for r in results)

    def test_search_case_insensitive(self, db):
        results = db.search("kirkland")
        assert len(results) >= 1

    def test_search_no_results(self, db):
        assert db.search("xyznonexistent") == []

    def test_search_matches_aliases(self, db):
        results = db.search("MoFo")
        assert len(results) >= 1
        assert any("Morrison" in r.canonical_name for r in results)


class TestFirmDatabaseFilters:
    """Test filtering by jurisdiction and type."""

    def test_by_jurisdiction_wisconsin(self, db):
        results = db.by_jurisdiction("wisconsin")
        assert len(results) >= 5  # We have several Wisconsin firms
        names = {r.canonical_name for r in results}
        assert "Foley & Lardner" in names

    def test_by_jurisdiction_federal(self, db):
        results = db.by_jurisdiction("federal")
        assert len(results) >= 10

    def test_by_type_government(self, db):
        results = db.by_type("government")
        assert len(results) >= 3  # DOJ, SG, all state AGs

    def test_by_type_boutique(self, db):
        results = db.by_type("boutique")
        assert len(results) >= 5  # Appellate specialists

    def test_by_type_legal_aid(self, db):
        results = db.by_type("legal_aid")
        assert len(results) >= 5


class TestFirmDatabaseFuzzyMatch:
    """Test fuzzy/token-based matching."""

    def test_fuzzy_match_ampersand_vs_and(self, db):
        """'&' and 'and' should be treated as equivalent."""
        record = db.lookup("Kirkland and Ellis")
        assert record is not None
        assert record.canonical_name == "Kirkland & Ellis"

    def test_fuzzy_match_partial_tokens(self, db):
        record = db.lookup("Gibson Dunn")
        assert record is not None
        assert "Gibson" in record.canonical_name


class TestFirmDatabaseCustom:
    """Test adding custom firms."""

    def test_add_custom_firm(self, db):
        custom = FirmRecord(
            canonical_name="Test Firm LLP",
            aliases=["Test Firm", "TF"],
            firm_type="boutique",
        )
        db.add_firm(custom)
        assert db.lookup("Test Firm LLP") is not None
        assert db.lookup("TF") is not None
        assert db.lookup("Test Firm") is not None


class TestFirmDatabaseCoverage:
    """Test that the database has adequate coverage."""

    def test_has_am_law_top_50(self, db):
        firms = db.all_firms()
        ranked = [f for f in firms if f.am_law_rank is not None and f.am_law_rank <= 50]
        assert len(ranked) == 50

    def test_has_all_50_state_ags(self, db):
        gov = db.by_type("government")
        ags = [r for r in gov if "Attorney General" in r.canonical_name]
        assert len(ags) >= 50

    def test_has_all_50_state_public_defenders(self, db):
        pds = db.by_type("public_defender")
        state_pds = [r for r in pds if "State Public Defender" in r.canonical_name]
        assert len(state_pds) >= 50

    def test_has_wisconsin_firms(self, db):
        wi = db.by_jurisdiction("wisconsin")
        names = {r.canonical_name for r in wi}
        assert "Michael Best & Friedrich" in names
        assert "Reinhart Boerner Van Deuren" in names

    def test_has_appellate_specialists(self, db):
        boutiques = db.by_type("boutique")
        assert any("Goldstein" in f.canonical_name for f in boutiques)
        assert any("Clement" in f.canonical_name for f in boutiques)


class TestFirmRecord:
    """Test FirmRecord data class."""

    def test_to_dict(self):
        record = FirmRecord(
            canonical_name="Test Firm",
            aliases=["TF"],
            firm_type="boutique",
            headquarters="NYC",
            primary_jurisdictions=["new_york"],
            practice_areas=["litigation"],
            am_law_rank=None,
            notable="Test",
        )
        d = record.to_dict()
        assert d["canonical_name"] == "Test Firm"
        assert d["aliases"] == ["TF"]
        assert d["firm_type"] == "boutique"
        assert d["headquarters"] == "NYC"
        assert d["notable"] == "Test"
