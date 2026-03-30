"""Tests for heading normalization engine."""

from legal_format_engine.engines.heading_engine import normalize_headings, normalize_single_heading
from legal_format_engine.models.document import HeadingLevel, Section
from legal_format_engine.rules.schema import HeadingRule


class TestNormalizeHeadings:
    def test_level_1_all_caps(self, wi_appellate_ruleset):
        sections = [
            Section(id="arg", heading_text="argument",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
            Section(id="conc", heading_text="conclusion",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
        ]
        result = normalize_headings(sections, wi_appellate_ruleset)
        assert result[0].heading_text == "Argument"
        assert result[1].heading_text == "Conclusion"
        # Level 1 has no numbering
        assert result[0].numbering_prefix == ""

    def test_already_correct(self, wi_appellate_ruleset):
        sections = [
            Section(id="arg", heading_text="ARGUMENT",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
        ]
        result = normalize_headings(sections, wi_appellate_ruleset)
        assert result[0].heading_text == "Argument"


class TestNormalizeSingle:
    def test_roman_prefix(self):
        rule = HeadingRule(level=2, case_style="title", alignment="left", numbering="roman")
        text, prefix = normalize_single_heading("standard of review", rule, index=0)
        assert text == "Standard of Review"
        assert prefix == "I."

    def test_alpha_prefix(self):
        rule = HeadingRule(level=3, case_style="sentence", alignment="left", numbering="alpha_upper")
        text, prefix = normalize_single_heading("THE EVIDENCE WAS SUFFICIENT", rule, index=1)
        assert text == "The evidence was sufficient"
        assert prefix == "B."

    def test_strips_existing_prefix(self):
        rule = HeadingRule(level=2, case_style="title", alignment="left", numbering="roman")
        text, prefix = normalize_single_heading("A. Standard of Review", rule, index=0)
        assert text == "Standard of Review"
        assert prefix == "I."
