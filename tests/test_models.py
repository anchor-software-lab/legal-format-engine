"""Tests for scraper data models and source reliability assessment."""

import pytest

from legal_format_engine.scraper.models import (
    CourtLevel,
    CourtSystem,
    EFilingRequirement,
    JurisdictionProfile,
    SourceReliability,
    SourceTier,
)


class TestSourceReliability:
    """Test the CRAAP-based reliability scoring."""

    def test_official_source_always_trustworthy(self):
        rel = SourceReliability(
            source_url="https://wicourts.gov/efiling",
            domain="wicourts.gov",
            tier=SourceTier.OFFICIAL,
            currency=0.5,
            relevance=0.5,
            authority=1.0,
            accuracy=0.5,
            purpose=1.0,
        )
        assert rel.is_trustworthy is True
        assert rel.needs_verification is False

    def test_quasi_official_needs_corroboration(self):
        rel = SourceReliability(
            source_url="https://efilinghelp.zendesk.com/article/123",
            domain="efilinghelp.zendesk.com",
            tier=SourceTier.QUASI_OFFICIAL,
            currency=0.8,
            relevance=0.8,
            authority=0.7,
            accuracy=0.7,
            purpose=0.8,
        )
        # Without corroboration, quasi-official with good score is not trustworthy
        assert rel.is_trustworthy is False

        # With corroboration
        rel.corroborated_by = ["https://wicourts.gov/efiling"]
        assert rel.is_trustworthy is True

    def test_tertiary_source_not_trustworthy(self):
        rel = SourceReliability(
            source_url="https://random-blog.com/wi-courts",
            domain="random-blog.com",
            tier=SourceTier.TERTIARY,
            currency=1.0,
            relevance=1.0,
            authority=0.15,
            accuracy=0.5,
            purpose=0.3,
        )
        assert rel.is_trustworthy is False
        assert rel.needs_verification is True

    def test_overall_score_weights_authority_double(self):
        rel = SourceReliability(
            source_url="https://example.gov/rules",
            domain="example.gov",
            tier=SourceTier.OFFICIAL,
            currency=0.8,
            relevance=0.8,
            authority=1.0,
            accuracy=0.8,
            purpose=0.8,
        )
        # Weighted: 0.8*1 + 0.8*1 + 1.0*2 + 0.8*1.5 + 0.8*0.5 = 5.2
        # Total weight: 1 + 1 + 2 + 1.5 + 0.5 = 6
        # Score: 5.2/6 = 0.867
        assert abs(rel.overall_score - 0.867) < 0.01

    def test_quasi_official_high_score_no_verification(self):
        rel = SourceReliability(
            source_url="https://efilinghelp.zendesk.com/article/123",
            domain="efilinghelp.zendesk.com",
            tier=SourceTier.QUASI_OFFICIAL,
            currency=0.9,
            relevance=0.9,
            authority=0.7,
            accuracy=0.8,
            purpose=0.8,
        )
        # Score should be >= 0.7, so no verification needed for quasi-official
        assert rel.overall_score >= 0.7
        assert rel.needs_verification is False


class TestEFilingRequirement:
    """Test e-filing requirement model."""

    def test_verified_with_reliable_source(self):
        rel = SourceReliability(
            source_url="https://wicourts.gov/rules",
            domain="wicourts.gov",
            tier=SourceTier.OFFICIAL,
            authority=1.0,
        )
        req = EFilingRequirement(
            court_system_id="abc123",
            jurisdiction="WI",
            category="margin",
            field="margin_top_inches",
            value=3.0,
            condition="proposed_order",
            description="3-inch top margin for proposed orders",
            source_url="https://wicourts.gov/rules",
            reliability=rel,
        )
        assert req.is_verified is True

    def test_not_verified_without_reliability(self):
        req = EFilingRequirement(
            court_system_id="abc123",
            jurisdiction="WI",
            category="margin",
            field="margin_top_inches",
            value=3.0,
            description="3-inch top margin",
            source_url="https://random.com",
        )
        assert req.is_verified is False


class TestJurisdictionProfile:
    """Test jurisdiction profile aggregation."""

    def test_add_requirement_updates_counts(self):
        profile = JurisdictionProfile(
            jurisdiction="WI",
            jurisdiction_name="Wisconsin",
        )
        official_rel = SourceReliability(
            source_url="https://wicourts.gov",
            domain="wicourts.gov",
            tier=SourceTier.OFFICIAL,
            authority=1.0,
        )
        req = EFilingRequirement(
            court_system_id="abc",
            jurisdiction="WI",
            category="margin",
            field="margin_top_inches",
            value=3.0,
            description="3-inch top margin",
            source_url="https://wicourts.gov",
            reliability=official_rel,
        )
        profile.add_requirement(req)
        assert profile.verified_requirement_count == 1
        assert profile.unverified_requirement_count == 0

    def test_to_ruleset_dict_only_includes_verified(self):
        profile = JurisdictionProfile(
            jurisdiction="WI",
            jurisdiction_name="Wisconsin",
        )
        # Add verified requirement
        official_rel = SourceReliability(
            source_url="https://wicourts.gov",
            domain="wicourts.gov",
            tier=SourceTier.OFFICIAL,
            authority=1.0,
        )
        profile.add_requirement(EFilingRequirement(
            court_system_id="abc",
            jurisdiction="WI",
            category="margin",
            field="margin_top_inches",
            value=3.0,
            condition="proposed_order",
            description="Verified requirement",
            source_url="https://wicourts.gov",
            reliability=official_rel,
        ))
        # Add unverified requirement
        profile.add_requirement(EFilingRequirement(
            court_system_id="abc",
            jurisdiction="WI",
            category="font",
            field="font_family",
            value="Comic Sans",
            description="Unverified requirement",
            source_url="https://random-blog.com",
            reliability=None,
        ))

        ruleset = profile.to_ruleset_dict()
        assert "proposed_order.margin_top_inches" in ruleset["rules"]
        assert "font_family" not in ruleset["rules"]

    def test_requirements_by_category(self):
        profile = JurisdictionProfile(
            jurisdiction="WI",
            jurisdiction_name="Wisconsin",
        )
        profile.requirements = [
            EFilingRequirement(
                court_system_id="a", jurisdiction="WI",
                category="margin", field="margin_top_inches",
                value=3.0, description="margin", source_url="http://x",
            ),
            EFilingRequirement(
                court_system_id="a", jurisdiction="WI",
                category="font", field="font_family",
                value="Arial", description="font", source_url="http://x",
            ),
            EFilingRequirement(
                court_system_id="a", jurisdiction="WI",
                category="margin", field="margin_left_inches",
                value=1.0, description="margin", source_url="http://x",
            ),
        ]
        margins = profile.requirements_by_category("margin")
        assert len(margins) == 2


class TestCourtSystem:
    """Test court system model."""

    def test_creation(self):
        court = CourtSystem(
            name="Wisconsin Circuit Court",
            jurisdiction="WI",
            state="WI",
            level=CourtLevel.CIRCUIT,
            parent_system="Wisconsin Court System",
            efiling_vendor="Tyler Technologies",
        )
        assert court.name == "Wisconsin Circuit Court"
        assert court.level == CourtLevel.CIRCUIT
        assert court.efiling_vendor == "Tyler Technologies"
