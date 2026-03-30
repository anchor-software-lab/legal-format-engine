"""Tests for rules/base.py - YAML ruleset loading."""

from __future__ import annotations

import pytest

from legal_format_engine.models.section import HeadingLevel, Ruleset
from legal_format_engine.rules.base import load_ruleset, list_rulesets


class TestLoadRuleset:
    """Tests for loading the Wisconsin appellate brief ruleset."""

    def test_loads_successfully(self, wi_ruleset):
        assert isinstance(wi_ruleset, Ruleset)

    def test_jurisdiction(self, wi_ruleset):
        assert wi_ruleset.jurisdiction == "wisconsin"

    def test_court_level(self, wi_ruleset):
        assert wi_ruleset.court_level == "court_of_appeals"

    def test_document_type(self, wi_ruleset):
        assert wi_ruleset.document_type == "appellate_brief"

    def test_name(self, wi_ruleset):
        assert "Wisconsin" in wi_ruleset.name

    def test_statute_reference(self, wi_ruleset):
        assert "809.19" in (wi_ruleset.statute_reference or "")

    # Page format
    def test_font(self, wi_ruleset):
        assert wi_ruleset.page_format.font == "Times New Roman"

    def test_font_size_13pt(self, wi_ruleset):
        assert wi_ruleset.page_format.font_size_pt == 13

    def test_line_spacing_double(self, wi_ruleset):
        assert wi_ruleset.page_format.line_spacing == "double"

    def test_margin_top_1_inch(self, wi_ruleset):
        assert wi_ruleset.page_format.margin_top_inches == 1.0

    def test_margin_bottom_1_inch(self, wi_ruleset):
        assert wi_ruleset.page_format.margin_bottom_inches == 1.0

    def test_margin_left_1_inch(self, wi_ruleset):
        assert wi_ruleset.page_format.margin_left_inches == 1.0

    def test_margin_right_1_inch(self, wi_ruleset):
        assert wi_ruleset.page_format.margin_right_inches == 1.0

    def test_page_dimensions(self, wi_ruleset):
        assert wi_ruleset.page_format.page_width_inches == 8.5
        assert wi_ruleset.page_format.page_height_inches == 11.0

    def test_first_line_indent(self, wi_ruleset):
        assert wi_ruleset.page_format.first_line_indent_inches == 0.5

    def test_hyphenation(self, wi_ruleset):
        assert wi_ruleset.page_format.hyphenation is True

    # Heading rules
    def test_heading_rules_count(self, wi_ruleset):
        assert len(wi_ruleset.heading_rules) == 4

    def test_heading_level1_style(self, wi_ruleset):
        hr1 = [hr for hr in wi_ruleset.heading_rules if hr.level == 1][0]
        assert hr1.style == HeadingLevel.TITLE_CASE_CENTERED

    def test_heading_level1_bold_centered(self, wi_ruleset):
        hr1 = [hr for hr in wi_ruleset.heading_rules if hr.level == 1][0]
        assert hr1.bold is True
        assert hr1.centered is True

    def test_heading_level2_roman(self, wi_ruleset):
        hr2 = [hr for hr in wi_ruleset.heading_rules if hr.level == 2][0]
        assert hr2.style == HeadingLevel.ROMAN_NUMERAL

    def test_heading_level3_capital_letter(self, wi_ruleset):
        hr3 = [hr for hr in wi_ruleset.heading_rules if hr.level == 3][0]
        assert hr3.style == HeadingLevel.CAPITAL_LETTER
        assert hr3.indent_inches == 0.5

    def test_heading_level4_arabic(self, wi_ruleset):
        hr4 = [hr for hr in wi_ruleset.heading_rules if hr.level == 4][0]
        assert hr4.style == HeadingLevel.ARABIC_NUMERAL
        assert hr4.bold is False

    # Section rules
    def test_section_rules_present(self, wi_ruleset):
        assert len(wi_ruleset.section_rules) >= 9

    def test_toc_required(self, wi_ruleset):
        toc = [s for s in wi_ruleset.section_rules if s.section_type == "table_of_contents"][0]
        assert toc.required is True
        assert toc.order == 1

    def test_argument_required(self, wi_ruleset):
        arg = [s for s in wi_ruleset.section_rules if s.section_type == "argument"][0]
        assert arg.required is True

    def test_case_facts_group(self, wi_ruleset):
        case = [s for s in wi_ruleset.section_rules if s.section_type == "statement_of_case"][0]
        assert case.group == "case_facts"

    def test_combined_case_facts_allowed(self, wi_ruleset):
        assert wi_ruleset.allow_combined_case_facts is True

    def test_word_limit(self, wi_ruleset):
        assert wi_ruleset.word_limit == 11000

    def test_page_limit_none(self, wi_ruleset):
        assert wi_ruleset.page_limit is None

    # Certification templates
    def test_cert_templates_count(self, wi_ruleset):
        assert len(wi_ruleset.certification_templates) >= 4

    def test_form_length_cert(self, wi_ruleset):
        fl = [ct for ct in wi_ruleset.certification_templates if ct.cert_type == "form_length"][0]
        assert "{word_count}" in fl.template

    def test_service_cert(self, wi_ruleset):
        svc = [ct for ct in wi_ruleset.certification_templates if ct.cert_type == "service"][0]
        assert svc.required is True

    # Aliases
    def test_issues_aliases(self, wi_ruleset):
        issues = [s for s in wi_ruleset.section_rules if s.section_type == "statement_of_issues"][0]
        assert "Issues Presented" in issues.aliases
        assert len(issues.aliases) >= 3

    def test_argument_aliases(self, wi_ruleset):
        arg = [s for s in wi_ruleset.section_rules if s.section_type == "argument"][0]
        assert "Argument" in arg.aliases


class TestLoadRulesetErrors:
    def test_nonexistent_jurisdiction(self):
        with pytest.raises(FileNotFoundError):
            load_ruleset("narnia", "appellate_brief")

    def test_nonexistent_document_type(self):
        with pytest.raises(FileNotFoundError):
            load_ruleset("wisconsin", "habeas_petition")

    def test_with_variant(self):
        with pytest.raises(FileNotFoundError):
            load_ruleset("wisconsin", "appellate_brief", variant="nonexistent")


class TestListRulesets:
    def test_returns_list(self):
        result = list_rulesets()
        assert isinstance(result, list)

    def test_has_wisconsin(self):
        result = list_rulesets()
        jurisdictions = {r["jurisdiction"] for r in result}
        assert "wisconsin" in jurisdictions

    def test_dict_keys(self):
        result = list_rulesets()
        for r in result:
            assert "jurisdiction" in r
            assert "document_type" in r
            assert "path" in r
