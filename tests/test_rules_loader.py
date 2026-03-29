"""Tests for rules loading."""

import pytest

from legal_format_engine.rules.loader import load_ruleset
from legal_format_engine.rules.schema import Ruleset


class TestLoadRuleset:
    def test_load_wi_appellate(self, wi_appellate_ruleset):
        assert wi_appellate_ruleset.jurisdiction == "wisconsin"
        assert wi_appellate_ruleset.court_level == "appellate"
        assert wi_appellate_ruleset.document_type == "brief"

    def test_page_format(self, wi_appellate_ruleset):
        fmt = wi_appellate_ruleset.page_format
        assert fmt.font_name == "Times New Roman"
        assert fmt.font_size_pt == 12
        assert fmt.line_spacing == 2.0
        assert fmt.margin_top_inches == 1.0

    def test_heading_rules(self, wi_appellate_ruleset):
        rules = wi_appellate_ruleset.heading_rules
        assert len(rules) == 4
        assert rules[0].level == 1
        assert rules[0].case_style == "upper"
        assert rules[0].alignment == "center"

    def test_required_sections(self, wi_appellate_ruleset):
        sections = wi_appellate_ruleset.required_sections
        assert len(sections) >= 6
        ids = [s.id for s in sections]
        assert "statement_of_issues" in ids
        assert "argument" in ids
        assert "conclusion" in ids

    def test_certifications(self, wi_appellate_ruleset):
        certs = wi_appellate_ruleset.certifications
        assert len(certs) >= 3
        cert_ids = [c.id for c in certs]
        assert "form_and_length" in cert_ids
        assert "certificate_of_service" in cert_ids

    def test_section_aliases(self, wi_appellate_ruleset):
        aliases = wi_appellate_ruleset.get_section_aliases()
        assert "Statement of Issues" in aliases["statement_of_issues"]
        assert "Issues Presented" in aliases["statement_of_issues"]

    def test_missing_ruleset(self):
        with pytest.raises(FileNotFoundError):
            load_ruleset("nonexistent", "court", "type")


class TestSPDRuleset:
    """Tests for the Wisconsin SPD appellate brief variant."""

    def test_load_spd_variant(self):
        rs = load_ruleset("wisconsin", "appellate", "brief", variant="spd")
        assert rs.jurisdiction == "wisconsin"
        assert rs.document_type == "brief"

    def test_spd_margins(self):
        rs = load_ruleset("wisconsin", "appellate", "brief", variant="spd")
        assert rs.page_format.margin_top_inches == 1.25
        assert rs.page_format.margin_left_inches == 2.0

    def test_spd_font_size(self):
        rs = load_ruleset("wisconsin", "appellate", "brief", variant="spd")
        assert rs.page_format.font_size_pt == 10

    def test_spd_case_and_facts_flexible(self):
        rs = load_ruleset("wisconsin", "appellate", "brief", variant="spd")
        ids = [s.id for s in rs.required_sections]
        # SPD accepts both combined and separate formats
        assert "statement_of_case_and_facts" in ids
        assert "statement_of_case" in ids
        assert "statement_of_facts" in ids
        # All are in the same group and individually optional
        case_facts_sections = [
            s for s in rs.required_sections if s.group == "case_facts"
        ]
        assert len(case_facts_sections) == 3
        assert all(not s.required for s in case_facts_sections)

    def test_spd_issues_presented(self):
        rs = load_ruleset("wisconsin", "appellate", "brief", variant="spd")
        issues = next(s for s in rs.required_sections if s.id == "statement_of_issues")
        assert issues.canonical_name == "Issues Presented"

    def test_spd_section_order(self):
        rs = load_ruleset("wisconsin", "appellate", "brief", variant="spd")
        # Sort by order; sections with same order are interchangeable
        by_order = sorted(rs.required_sections, key=lambda s: s.order)
        orders = [s.order for s in by_order]
        # Orders should be non-decreasing
        assert orders == sorted(orders)
        # First few should be in expected sequence
        first_ids = [s.id for s in by_order if s.order <= 4]
        assert first_ids == [
            "table_of_contents",
            "table_of_authorities",
            "statement_of_issues",
            "position_on_oral_argument",
        ]

    def test_spd_certifications(self):
        rs = load_ruleset("wisconsin", "appellate", "brief", variant="spd")
        cert_ids = [c.id for c in rs.certifications]
        assert "form_and_length" in cert_ids
        assert "appendix_certification" in cert_ids

    def test_spd_heading_level_1_centered(self):
        rs = load_ruleset("wisconsin", "appellate", "brief", variant="spd")
        h1 = rs.get_heading_rule(1)
        assert h1.alignment == "center"
        assert h1.bold is True

    def test_variant_fallback(self):
        """Unknown variant falls back to generic ruleset."""
        rs = load_ruleset("wisconsin", "appellate", "brief", variant="nonexistent")
        assert rs.jurisdiction == "wisconsin"
        # Falls back to generic which has 1.0" margins
        assert rs.page_format.margin_top_inches == 1.0
