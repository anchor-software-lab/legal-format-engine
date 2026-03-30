"""Tests for the synthesizer module."""

import pytest
from anchor_ml_engine.synthesizer import (
    synthesize_ruleset,
    diff_against_ruleset,
    _section_id_to_name,
)
from anchor_ml_engine.models import (
    LearnedFormat,
    LearnedHeadingStyle,
    LearnedSectionOrder,
    LearnedValue,
)


class TestSynthesizeRuleset:
    def test_empty_learned(self):
        learned = LearnedFormat()
        ruleset = synthesize_ruleset(learned)
        assert "category" in ruleset
        assert ruleset["_ml_metadata"]["document_count"] == 0

    def test_with_font_and_margins(self):
        learned = LearnedFormat(
            document_count=5,
            font_family=LearnedValue(value="Times New Roman", confidence=0.8,
                                     sample_count=5, agreement=0.9),
            font_size_pt=LearnedValue(value=12.0, confidence=0.9,
                                      sample_count=5, agreement=1.0),
            margin_top=LearnedValue(value=1.0, confidence=0.7,
                                    sample_count=5, agreement=0.8),
        )
        ruleset = synthesize_ruleset(learned, category="test")
        assert ruleset["page_format"]["font_name"] == "Times New Roman"
        assert ruleset["page_format"]["font_size_pt"] == 12.0
        assert ruleset["page_format"]["margin_top_inches"] == 1.0

    def test_low_confidence_excluded(self):
        learned = LearnedFormat(
            document_count=1,
            font_family=LearnedValue(value="Arial", confidence=0.1,
                                     sample_count=1, agreement=0.5),
        )
        ruleset = synthesize_ruleset(learned)
        assert "font_name" not in ruleset.get("page_format", {})

    def test_heading_rules_generated(self):
        learned = LearnedFormat(
            document_count=5,
            heading_styles=[
                LearnedHeadingStyle(
                    level=1,
                    case_style=LearnedValue(value="upper", confidence=0.8,
                                            sample_count=5, agreement=0.9),
                    alignment=LearnedValue(value="center", confidence=0.8,
                                           sample_count=5, agreement=0.9),
                    bold=LearnedValue(value="1.0", confidence=0.8,
                                      sample_count=5, agreement=0.9),
                ),
            ],
        )
        ruleset = synthesize_ruleset(learned)
        assert len(ruleset["heading_rules"]) == 1
        assert ruleset["heading_rules"][0]["case_style"] == "upper"

    def test_sections_generated(self):
        learned = LearnedFormat(
            document_count=5,
            section_order=[
                LearnedSectionOrder(id="argument", frequency=1.0, median_order=0),
                LearnedSectionOrder(id="conclusion", frequency=0.8, median_order=1),
                LearnedSectionOrder(id="rare_section", frequency=0.1, median_order=2),
            ],
        )
        ruleset = synthesize_ruleset(learned)
        sections = ruleset["required_sections"]
        assert len(sections) == 2  # rare_section excluded (freq < 0.3)
        assert sections[0]["id"] == "argument"
        assert sections[0]["required"] is True
        assert sections[1]["id"] == "conclusion"
        assert sections[1]["required"] is True


class TestDiffAgainstRuleset:
    def test_no_diff_when_matching(self):
        learned = LearnedFormat(
            font_family=LearnedValue(value="Times New Roman", confidence=0.9,
                                     sample_count=10, agreement=0.95),
        )
        existing = {"page_format": {"font_name": "Times New Roman"}}
        recs = diff_against_ruleset(learned, existing)
        assert len(recs) == 0

    def test_diff_when_different(self):
        learned = LearnedFormat(
            font_family=LearnedValue(value="Arial", confidence=0.9,
                                     sample_count=10, agreement=0.95),
        )
        existing = {"page_format": {"font_name": "Times New Roman"}}
        recs = diff_against_ruleset(learned, existing)
        assert len(recs) == 1
        assert recs[0].suggested_value == "Arial"
        assert recs[0].current_value == "Times New Roman"

    def test_low_confidence_no_recommendation(self):
        learned = LearnedFormat(
            font_family=LearnedValue(value="Arial", confidence=0.3,
                                     sample_count=2, agreement=0.5),
        )
        existing = {"page_format": {"font_name": "Times New Roman"}}
        recs = diff_against_ruleset(learned, existing)
        assert len(recs) == 0  # below override confidence threshold


class TestSectionIdToName:
    def test_known_sections(self):
        assert _section_id_to_name("argument") == "Argument"
        assert _section_id_to_name("table_of_contents") == "Table of Contents"
        assert _section_id_to_name("conclusion") == "Conclusion"

    def test_unknown_section(self):
        assert _section_id_to_name("custom_section") == "Custom Section"
