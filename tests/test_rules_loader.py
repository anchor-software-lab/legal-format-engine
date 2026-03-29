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
        assert fmt.font_size_pt == 10
        assert fmt.line_spacing == 2.0
        assert fmt.margin_top_inches == 1.25
        assert fmt.margin_left_inches == 2.0

    def test_heading_rules(self, wi_appellate_ruleset):
        rules = wi_appellate_ruleset.heading_rules
        assert len(rules) == 4
        assert rules[0].level == 1
        assert rules[0].case_style == "title"
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
        assert len(certs) >= 2
        cert_ids = [c.id for c in certs]
        assert "form_and_length" in cert_ids
        assert "appendix_certification" in cert_ids

    def test_section_aliases(self, wi_appellate_ruleset):
        aliases = wi_appellate_ruleset.get_section_aliases()
        assert "Statement of Issues" in aliases["statement_of_issues"]
        assert "Issues Presented" in aliases["statement_of_issues"]

    def test_missing_ruleset(self):
        with pytest.raises(FileNotFoundError):
            load_ruleset("nonexistent", "court", "type")


class TestWisconsinAppellateFormat:
    """Tests for the Wisconsin appellate brief default format."""

    def test_margins(self):
        rs = load_ruleset("wisconsin", "appellate", "brief")
        assert rs.page_format.margin_top_inches == 1.25
        assert rs.page_format.margin_left_inches == 2.0

    def test_font_size(self):
        rs = load_ruleset("wisconsin", "appellate", "brief")
        assert rs.page_format.font_size_pt == 10

    def test_case_and_facts_flexible(self):
        rs = load_ruleset("wisconsin", "appellate", "brief")
        ids = [s.id for s in rs.required_sections]
        # Accepts both combined and separate formats
        assert "statement_of_case_and_facts" in ids
        assert "statement_of_case" in ids
        assert "statement_of_facts" in ids
        # All are in the same group and individually optional
        case_facts_sections = [
            s for s in rs.required_sections if s.group == "case_facts"
        ]
        assert len(case_facts_sections) == 3
        assert all(not s.required for s in case_facts_sections)

    def test_issues_presented(self):
        rs = load_ruleset("wisconsin", "appellate", "brief")
        issues = next(s for s in rs.required_sections if s.id == "statement_of_issues")
        assert issues.canonical_name == "Issues Presented"

    def test_section_order(self):
        rs = load_ruleset("wisconsin", "appellate", "brief")
        by_order = sorted(rs.required_sections, key=lambda s: s.order)
        orders = [s.order for s in by_order]
        assert orders == sorted(orders)
        first_ids = [s.id for s in by_order if s.order <= 4]
        assert first_ids == [
            "table_of_contents",
            "table_of_authorities",
            "statement_of_issues",
            "position_on_oral_argument",
        ]

    def test_certifications(self):
        rs = load_ruleset("wisconsin", "appellate", "brief")
        cert_ids = [c.id for c in rs.certifications]
        assert "form_and_length" in cert_ids
        assert "appendix_certification" in cert_ids

    def test_heading_level_1_centered(self):
        rs = load_ruleset("wisconsin", "appellate", "brief")
        h1 = rs.get_heading_rule(1)
        assert h1.alignment == "center"
        assert h1.bold is True

    def test_variant_fallback(self):
        """Unknown variant falls back to default ruleset."""
        rs = load_ruleset("wisconsin", "appellate", "brief", variant="nonexistent")
        assert rs.jurisdiction == "wisconsin"
        assert rs.page_format.margin_top_inches == 1.25
