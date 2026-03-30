"""Tests for the firm_database module."""

import pytest
from anchor_ml_engine.firm_database import FirmDatabase, FirmRecord


class TestFirmDatabase:
    def setup_method(self):
        self.db = FirmDatabase()

    def test_total_firm_count(self):
        """Verify 160+ firms are loaded."""
        all_firms = self.db.all_firms()
        assert len(all_firms) >= 160

    def test_lookup_by_canonical_name(self):
        record = self.db.lookup("Kirkland & Ellis")
        assert record is not None
        assert record.canonical_name == "Kirkland & Ellis"
        assert record.am_law_rank == 1

    def test_lookup_by_alias(self):
        record = self.db.lookup("Kirkland & Ellis LLP")
        assert record is not None
        assert record.canonical_name == "Kirkland & Ellis"

    def test_lookup_by_short_alias(self):
        record = self.db.lookup("Skadden")
        assert record is not None
        assert "Skadden" in record.canonical_name

    def test_lookup_not_found(self):
        record = self.db.lookup("Nonexistent Firm LLP")
        assert record is None

    def test_normalize_name(self):
        assert self.db.normalize_name("Kirkland & Ellis LLP") == "Kirkland & Ellis"
        assert self.db.normalize_name("Unknown Firm") == "Unknown Firm"

    def test_search(self):
        results = self.db.search("Kirkland")
        assert len(results) >= 1
        assert any(r.canonical_name == "Kirkland & Ellis" for r in results)

    def test_by_jurisdiction(self):
        wi_firms = self.db.by_jurisdiction("wisconsin")
        assert len(wi_firms) >= 5  # Multiple WI firms loaded

    def test_by_type_government(self):
        gov_firms = self.db.by_type("government")
        assert len(gov_firms) >= 50  # 50 state AGs + federal

    def test_by_type_public_defender(self):
        pd_firms = self.db.by_type("public_defender")
        assert len(pd_firms) >= 50  # 50 state PDs + federal

    def test_fuzzy_match(self):
        record = self.db.lookup("Foley Lardner")
        assert record is not None
        assert record.canonical_name == "Foley & Lardner"

    def test_add_firm(self):
        custom = FirmRecord(
            canonical_name="Test Firm LLP",
            aliases=["Test Firm"],
            firm_type="boutique",
        )
        self.db.add_firm(custom)
        result = self.db.lookup("Test Firm LLP")
        assert result is not None
        assert result.canonical_name == "Test Firm LLP"

    def test_firm_record_to_dict(self):
        record = self.db.lookup("Kirkland & Ellis")
        d = record.to_dict()
        assert d["canonical_name"] == "Kirkland & Ellis"
        assert "aliases" in d
        assert "am_law_rank" in d

    def test_normalize_key_strips_suffixes(self):
        key = FirmDatabase._normalize_key("Smith & Jones, LLP")
        assert "llp" not in key
        assert "and" in key  # & -> "and"

    def test_wisconsin_firms(self):
        wi = self.db.by_jurisdiction("wisconsin")
        names = {r.canonical_name for r in wi}
        assert "Foley & Lardner" in names
        assert "Michael Best & Friedrich" in names

    def test_scotus_specialists(self):
        results = self.db.search("Goldstein")
        assert any("Goldstein" in r.canonical_name for r in results)
