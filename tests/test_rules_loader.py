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
