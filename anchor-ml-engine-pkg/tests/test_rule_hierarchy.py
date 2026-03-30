"""Tests for the rule_hierarchy module."""

import pytest
from anchor_ml_engine.rule_hierarchy import (
    RULE_GOVERNED_FIELDS,
    identify_rule_governed_fields,
    resolve_format,
)
from anchor_ml_engine.models import (
    LearnedFormat,
    LearnedValue,
    StylePreference,
    StyleProfile,
)


class TestRuleGovernedFields:
    def test_key_fields_present(self):
        assert "font_name" in RULE_GOVERNED_FIELDS
        assert "font_size_pt" in RULE_GOVERNED_FIELDS
        assert "line_spacing" in RULE_GOVERNED_FIELDS
        assert "margin_top_inches" in RULE_GOVERNED_FIELDS


class TestIdentifyRuleGovernedFields:
    def test_page_format_governed(self):
        rules = {
            "page_format": {
                "font_name": "Times New Roman",
                "font_size_pt": 12,
                "line_spacing": 2.0,
                "margin_top_inches": 1.0,
            }
        }
        governed = identify_rule_governed_fields(rules)
        assert "font_name" in governed
        assert "font_size_pt" in governed
        assert "line_spacing" in governed
        assert "margin_top_inches" in governed

    def test_heading_rules_governed(self):
        rules = {
            "heading_rules": [
                {"level": 1, "case_style": "upper", "alignment": "center", "bold": True},
            ]
        }
        governed = identify_rule_governed_fields(rules)
        assert "heading_1_case_style" in governed
        assert "heading_1_alignment" in governed
        assert "heading_1_bold" in governed

    def test_empty_rules(self):
        governed = identify_rule_governed_fields({})
        assert len(governed) == 0


class TestResolveFormat:
    def test_rules_always_win(self):
        rules = {
            "page_format": {
                "font_name": "Times New Roman",
                "font_size_pt": 12,
                "line_spacing": 2.0,
                "margin_top_inches": 1.0,
                "margin_bottom_inches": 1.0,
                "margin_left_inches": 1.0,
                "margin_right_inches": 1.0,
            }
        }
        # ML says 13pt but rule says 12pt
        learned = LearnedFormat(
            font_size_pt=LearnedValue(value=13.0, confidence=0.95,
                                      sample_count=100, agreement=0.99),
        )
        resolved = resolve_format(rules, learned)
        font_decision = resolved.get("font_size_pt")
        assert font_decision is not None
        assert font_decision.value == 12
        assert font_decision.source == "rule"

    def test_ml_fills_discretionary(self):
        rules = {"page_format": {}}
        learned = LearnedFormat(
            body_indent=LearnedValue(value=0.3, confidence=0.8,
                                     sample_count=10, agreement=0.9),
        )
        resolved = resolve_format(rules, learned)
        indent_decision = resolved.get("body_first_line_indent")
        assert indent_decision is not None
        assert indent_decision.value == 0.3
        assert indent_decision.source == "ml_learned"

    def test_style_profile_fills_gap(self):
        rules = {"page_format": {}}
        style = StyleProfile(
            profile_type="author",
            name="Test",
            preferences=[
                StylePreference(
                    field="heading_space_before_pt",
                    value=18.0,
                    sample_count=5,
                    consistency=0.8,
                ),
            ],
        )
        resolved = resolve_format(rules, None, style)
        spacing = resolved.get("heading_space_before_pt")
        assert spacing is not None
        assert spacing.value == 18.0
        assert spacing.source == "style_profile"

    def test_default_fallback(self):
        rules = {"page_format": {}}
        resolved = resolve_format(rules)
        indent = resolved.get("body_first_line_indent")
        assert indent is not None
        assert indent.value == 0.5  # engine default
        assert indent.source == "default"

    def test_hierarchy_ml_over_style(self):
        """ML should win over style profile."""
        rules = {"page_format": {}}
        learned = LearnedFormat(
            body_indent=LearnedValue(value=0.3, confidence=0.8,
                                     sample_count=10, agreement=0.9),
        )
        style = StyleProfile(
            profile_type="author",
            name="Test",
            preferences=[
                StylePreference(
                    field="body_first_line_indent",
                    value=0.5,
                    sample_count=5,
                    consistency=0.9,
                ),
            ],
        )
        resolved = resolve_format(rules, learned, style)
        indent = resolved.get("body_first_line_indent")
        assert indent.value == 0.3
        assert indent.source == "ml_learned"

    def test_resolved_format_to_dict(self):
        rules = {
            "category": "test",
            "subcategory": "default",
            "document_type": "report",
            "page_format": {"font_name": "Arial"},
        }
        resolved = resolve_format(rules)
        d = resolved.to_dict()
        assert d["category"] == "test"
        assert "decisions" in d
        assert "summary" in d

    def test_heading_numbering_default(self):
        rules = {"page_format": {}}
        resolved = resolve_format(rules)
        # Level 2 default numbering should be "roman"
        h2_numbering = resolved.get("heading_2_numbering")
        assert h2_numbering is not None
        assert h2_numbering.value == "roman"
        assert h2_numbering.source == "default"

    def test_decision_counts(self):
        rules = {
            "page_format": {
                "font_name": "Arial",
                "font_size_pt": 12,
            }
        }
        resolved = resolve_format(rules)
        assert resolved.rule_count >= 2
        assert resolved.default_count >= 1
