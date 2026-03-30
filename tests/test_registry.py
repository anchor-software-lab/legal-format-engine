"""Tests for the jurisdiction registry."""

from legal_format_engine.scraper.models import CourtLevel
from legal_format_engine.scraper.registry import JurisdictionRegistry


class TestJurisdictionRegistry:
    """Test registry lookups."""

    def test_wisconsin_in_registry(self):
        reg = JurisdictionRegistry()
        courts = reg.by_jurisdiction("WI")
        assert len(courts) >= 1
        names = [c.name for c in courts]
        assert "Wisconsin Circuit Court" in names

    def test_federal_in_registry(self):
        reg = JurisdictionRegistry()
        courts = reg.by_jurisdiction("US-FED")
        assert len(courts) >= 1

    def test_by_state(self):
        reg = JurisdictionRegistry()
        wi_courts = reg.by_state("WI")
        assert len(wi_courts) >= 1
        assert all(c.state == "WI" for c in wi_courts)

    def test_by_level(self):
        reg = JurisdictionRegistry()
        circuits = reg.by_level(CourtLevel.CIRCUIT)
        assert len(circuits) >= 3  # WI, CA, TX, IL, FL, etc.

    def test_by_vendor_tyler(self):
        reg = JurisdictionRegistry()
        tyler_courts = reg.by_vendor("Tyler Technologies")
        assert len(tyler_courts) >= 3  # WI, TX, IL, MN, etc.

    def test_all_requirements_urls(self):
        reg = JurisdictionRegistry()
        urls = reg.all_requirements_urls()
        assert "WI" in urls
        assert len(urls["WI"]) >= 1

    def test_jurisdictions_list(self):
        reg = JurisdictionRegistry()
        jurisdictions = reg.jurisdictions
        assert "WI" in jurisdictions
        assert "US-FED" in jurisdictions
        assert "CA" in jurisdictions

    def test_add_entry(self):
        reg = JurisdictionRegistry()
        before = len(reg.all_courts())
        reg.add_entry(
            jurisdiction="TEST",
            jurisdiction_name="Test State",
            court_name="Test Court",
            level=CourtLevel.CIRCUIT,
        )
        after = len(reg.all_courts())
        assert after == before + 1

    def test_states_list(self):
        reg = JurisdictionRegistry()
        states = reg.states
        assert "WI" in states
        assert "CA" in states
        assert len(states) >= 8  # WI, CA, TX, NY, IL, FL, MN, MI, IA
