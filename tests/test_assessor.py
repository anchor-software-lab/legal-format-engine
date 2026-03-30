"""Tests for the source reliability assessor."""

import pytest

from legal_format_engine.scraper.assessor import ReliabilityAssessor
from legal_format_engine.scraper.models import (
    EFilingRequirement,
    SourceReliability,
    SourceTier,
)


@pytest.fixture
def assessor():
    return ReliabilityAssessor()


class TestCurrencyAssessment:
    """Test temporal currency scoring."""

    def test_recent_date_scores_high(self, assessor):
        rel = SourceReliability(
            source_url="https://example.gov",
            domain="example.gov",
            tier=SourceTier.OFFICIAL,
        )
        # Use a very recent ISO date
        from datetime import datetime, timezone, timedelta
        recent = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        result = assessor.assess_page(rel, "e-filing requirements", recent)
        assert result.currency == 1.0

    def test_unknown_date_moderate_penalty(self, assessor):
        rel = SourceReliability(
            source_url="https://example.gov",
            domain="example.gov",
            tier=SourceTier.OFFICIAL,
        )
        result = assessor.assess_page(rel, "some text", None)
        assert result.currency == 0.4

    def test_stale_date_low_score(self, assessor):
        rel = SourceReliability(
            source_url="https://example.gov",
            domain="example.gov",
            tier=SourceTier.OFFICIAL,
        )
        result = assessor.assess_page(rel, "some text", "2020-01-01T00:00:00+00:00")
        assert result.currency == 0.3


class TestRelevanceAssessment:
    """Test content relevance scoring."""

    def test_efiling_content_scores_high(self, assessor):
        rel = SourceReliability(
            source_url="https://example.gov",
            domain="example.gov",
            tier=SourceTier.OFFICIAL,
        )
        text = """
        Electronic filing requirements for proposed orders in circuit court.
        Margin requirements: 3-inch top margin. Font must be Arial 12pt.
        File format: .docx for proposed orders, .pdf for all other documents.
        """
        result = assessor.assess_page(rel, text, None)
        assert result.relevance >= 0.5

    def test_irrelevant_content_scores_low(self, assessor):
        rel = SourceReliability(
            source_url="https://example.gov",
            domain="example.gov",
            tier=SourceTier.OFFICIAL,
        )
        text = "Welcome to the court website. Contact us for information."
        result = assessor.assess_page(rel, text, None)
        assert result.relevance <= 0.2


class TestAccuracyAssessment:
    """Test content specificity/accuracy scoring."""

    def test_specific_requirements_score_high(self, assessor):
        rel = SourceReliability(
            source_url="https://example.gov",
            domain="example.gov",
            tier=SourceTier.OFFICIAL,
        )
        text = """
        Documents must have 1-inch margins. Font shall be 12pt.
        Submit in .docx format. This is a mandatory requirement.
        """
        result = assessor.assess_page(rel, text, None)
        assert result.accuracy >= 0.4

    def test_vague_content_scores_lower(self, assessor):
        rel = SourceReliability(
            source_url="https://example.gov",
            domain="example.gov",
            tier=SourceTier.OFFICIAL,
        )
        text = """
        You may want to consider using appropriate margins.
        Generally, documents should be formatted properly.
        Contact the clerk for more information.
        """
        result = assessor.assess_page(rel, text, None)
        assert result.accuracy <= 0.2


class TestCrossReference:
    """Test cross-referencing between sources."""

    def test_matching_requirements_corroborated(self, assessor):
        rel1 = SourceReliability(
            source_url="https://source1.gov",
            domain="source1.gov",
            tier=SourceTier.OFFICIAL,
        )
        rel2 = SourceReliability(
            source_url="https://source2.gov",
            domain="source2.gov",
            tier=SourceTier.OFFICIAL,
        )
        req1 = EFilingRequirement(
            court_system_id="a", jurisdiction="WI",
            category="margin", field="margin_top_inches",
            value=3.0, condition="proposed_order",
            description="3-inch margin",
            source_url="https://source1.gov",
            reliability=rel1,
        )
        req2 = EFilingRequirement(
            court_system_id="a", jurisdiction="WI",
            category="margin", field="margin_top_inches",
            value=3.0, condition="proposed_order",
            description="3-inch margin",
            source_url="https://source2.gov",
            reliability=rel2,
        )
        assessor.cross_reference(req1, [req2])
        assert "https://source2.gov" in req1.reliability.corroborated_by

    def test_conflicting_requirements_flagged(self, assessor):
        rel1 = SourceReliability(
            source_url="https://source1.gov",
            domain="source1.gov",
            tier=SourceTier.OFFICIAL,
        )
        rel2 = SourceReliability(
            source_url="https://source2.gov",
            domain="source2.gov",
            tier=SourceTier.OFFICIAL,
        )
        req1 = EFilingRequirement(
            court_system_id="a", jurisdiction="WI",
            category="margin", field="margin_top_inches",
            value=3.0, condition="proposed_order",
            description="3-inch margin",
            source_url="https://source1.gov",
            reliability=rel1,
        )
        req2 = EFilingRequirement(
            court_system_id="a", jurisdiction="WI",
            category="margin", field="margin_top_inches",
            value=2.0, condition="proposed_order",
            description="2-inch margin",
            source_url="https://source2.gov",
            reliability=rel2,
        )
        assessor.cross_reference(req1, [req2])
        assert "https://source2.gov" in req1.reliability.contradicted_by

    def test_different_fields_not_compared(self, assessor):
        rel1 = SourceReliability(
            source_url="https://source1.gov",
            domain="source1.gov",
            tier=SourceTier.OFFICIAL,
        )
        req1 = EFilingRequirement(
            court_system_id="a", jurisdiction="WI",
            category="margin", field="margin_top_inches",
            value=3.0, description="top", source_url="https://source1.gov",
            reliability=rel1,
        )
        req2 = EFilingRequirement(
            court_system_id="a", jurisdiction="WI",
            category="margin", field="margin_left_inches",
            value=1.0, description="left", source_url="https://source2.gov",
        )
        assessor.cross_reference(req1, [req2])
        assert len(req1.reliability.corroborated_by) == 0
        assert len(req1.reliability.contradicted_by) == 0


class TestReliabilityReport:
    """Test reliability report generation."""

    def test_report_structure(self, assessor):
        rel = SourceReliability(
            source_url="https://wicourts.gov",
            domain="wicourts.gov",
            tier=SourceTier.OFFICIAL,
        )
        assessor.assess_page(rel, "e-filing requirements", None)
        report = assessor.generate_report()
        assert report["total_sources_assessed"] == 1
        assert report["by_tier"]["official"] == 1
        assert "sources" in report
