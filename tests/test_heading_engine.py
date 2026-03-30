"""Tests for engines/heading_engine.py."""

from __future__ import annotations

import pytest

from legal_format_engine.engines.heading_engine import (
    _apply_case,
    _style_to_numbering,
    normalize_headings,
)
from legal_format_engine.models.document import Section
from legal_format_engine.models.section import HeadingLevel, HeadingRule, Ruleset


class TestApplyCase:
    def test_all_caps_centered(self):
        assert _apply_case("argument", HeadingLevel.ALL_CAPS_CENTERED) == "ARGUMENT"

    def test_all_caps_left(self):
        assert _apply_case("argument", HeadingLevel.ALL_CAPS_LEFT) == "ARGUMENT"

    def test_title_case_centered(self):
        assert _apply_case("statement of the case", HeadingLevel.TITLE_CASE_CENTERED) == "Statement of the Case"

    def test_title_case_left(self):
        assert _apply_case("table of contents", HeadingLevel.TITLE_CASE_LEFT) == "Table of Contents"

    def test_sentence_case(self):
        assert _apply_case("THE ARGUMENT", HeadingLevel.SENTENCE_CASE) == "The argument"

    def test_roman_numeral_uses_title(self):
        assert _apply_case("standard of review", HeadingLevel.ROMAN_NUMERAL) == "Standard of Review"

    def test_capital_letter_uses_title(self):
        assert _apply_case("first point", HeadingLevel.CAPITAL_LETTER) == "First Point"

    def test_arabic_numeral_uses_title(self):
        assert _apply_case("sub point", HeadingLevel.ARABIC_NUMERAL) == "Sub Point"


class TestStyleToNumbering:
    def test_roman(self):
        assert _style_to_numbering(HeadingLevel.ROMAN_NUMERAL) == "roman"

    def test_alpha(self):
        assert _style_to_numbering(HeadingLevel.CAPITAL_LETTER) == "alpha"

    def test_arabic(self):
        assert _style_to_numbering(HeadingLevel.ARABIC_NUMERAL) == "arabic"

    def test_title_case_returns_none(self):
        assert _style_to_numbering(HeadingLevel.TITLE_CASE_CENTERED) is None

    def test_all_caps_returns_none(self):
        assert _style_to_numbering(HeadingLevel.ALL_CAPS_CENTERED) is None


class TestNormalizeHeadings:
    def test_level1_title_case(self, minimal_ruleset):
        sections = [
            Section(section_type="arg", heading="ARGUMENT", heading_level=1),
        ]
        result = normalize_headings(sections, minimal_ruleset)
        assert result[0].heading == "Argument"

    def test_level1_no_numbering(self, minimal_ruleset):
        sections = [
            Section(section_type="arg", heading="ARGUMENT", heading_level=1),
        ]
        result = normalize_headings(sections, minimal_ruleset)
        assert result[0].numbering_prefix is None

    def test_level2_roman_numbering(self, minimal_ruleset):
        sections = [
            Section(section_type="sub1", heading="First Point", heading_level=2),
            Section(section_type="sub2", heading="Second Point", heading_level=2),
        ]
        result = normalize_headings(sections, minimal_ruleset)
        assert result[0].numbering_prefix == "I."
        assert result[1].numbering_prefix == "II."

    def test_level3_alpha_numbering(self, minimal_ruleset):
        sections = [
            Section(section_type="sub", heading="detail one", heading_level=3),
            Section(section_type="sub", heading="detail two", heading_level=3),
        ]
        result = normalize_headings(sections, minimal_ruleset)
        assert result[0].numbering_prefix == "A."
        assert result[1].numbering_prefix == "B."

    def test_level4_arabic_numbering(self, minimal_ruleset):
        sections = [
            Section(section_type="sub", heading="sub point", heading_level=4),
        ]
        result = normalize_headings(sections, minimal_ruleset)
        assert result[0].numbering_prefix == "1."

    def test_strips_existing_prefix(self, minimal_ruleset):
        sections = [
            Section(section_type="sub", heading="III. Old Heading", heading_level=2),
        ]
        result = normalize_headings(sections, minimal_ruleset)
        # Should strip III. and reapply I. (first L2 section)
        assert result[0].numbering_prefix == "I."
        assert "III" not in result[0].heading

    def test_subsection_counters_reset(self, minimal_ruleset):
        parent1 = Section(
            section_type="arg", heading="Argument", heading_level=1,
            subsections=[
                Section(section_type="sub", heading="Point A", heading_level=2),
                Section(section_type="sub", heading="Point B", heading_level=2),
            ],
        )
        parent2 = Section(
            section_type="conc", heading="Conclusion", heading_level=1,
            subsections=[
                Section(section_type="sub", heading="Point C", heading_level=2),
            ],
        )
        result = normalize_headings([parent1, parent2], minimal_ruleset)
        # Subsection counter should reset for each parent
        assert result[0].subsections[0].numbering_prefix == "I."
        assert result[0].subsections[1].numbering_prefix == "II."
        assert result[1].subsections[0].numbering_prefix == "I."

    def test_no_rule_for_level(self, minimal_ruleset):
        sections = [
            Section(section_type="x", heading="Deep Heading", heading_level=5),
        ]
        result = normalize_headings(sections, minimal_ruleset)
        # Level 5 has no rule, should be unchanged
        assert result[0].heading == "Deep Heading"

    def test_empty_sections_list(self, minimal_ruleset):
        result = normalize_headings([], minimal_ruleset)
        assert result == []

    def test_multiple_level1_headings(self, minimal_ruleset):
        sections = [
            Section(section_type="toc", heading="TABLE OF CONTENTS", heading_level=1),
            Section(section_type="arg", heading="ARGUMENT", heading_level=1),
            Section(section_type="conc", heading="CONCLUSION", heading_level=1),
        ]
        result = normalize_headings(sections, minimal_ruleset)
        assert result[0].heading == "Table of Contents"
        assert result[1].heading == "Argument"
        assert result[2].heading == "Conclusion"
        for s in result:
            assert s.numbering_prefix is None
