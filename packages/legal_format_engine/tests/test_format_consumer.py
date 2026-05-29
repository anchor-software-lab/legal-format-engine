"""Tests for the ML format consumer — the public-side integration."""

import json
import tempfile
from pathlib import Path

from legal_format_engine.ml_integration.format_consumer import (
    FormatSpec,
    load_format_spec,
    merge_with_rules,
)


def _make_export_json() -> dict:
    """Simulates what the ML engine's export_learned_format() produces."""
    return {
        "_export_metadata": {
            "exported_at": "2026-03-30T20:00:00Z",
            "engine_version": "0.1.0",
            "document_count": 3,
            "overall_confidence": 0.72,
            "governance": "format-only export — no document content included",
        },
        "typography": {
            "font_family": {"value": "Times New Roman", "confidence": 0.9, "sample_count": 3, "agreement": 1.0},
            "font_size_pt": {"value": 13.0, "confidence": 0.85, "sample_count": 3, "agreement": 0.95},
            "line_spacing": {"value": 2.0, "confidence": 0.9, "sample_count": 3, "agreement": 1.0},
        },
        "layout": {
            "margin_top": {"value": 1.0, "confidence": 0.8, "sample_count": 3, "agreement": 0.9},
            "margin_bottom": {"value": 1.0, "confidence": 0.8, "sample_count": 3, "agreement": 0.9},
            "margin_left": {"value": 1.25, "confidence": 0.75, "sample_count": 3, "agreement": 0.85},
            "margin_right": {"value": 1.0, "confidence": 0.8, "sample_count": 3, "agreement": 0.9},
        },
        "headings": [
            {
                "level": 1,
                "case_style": {"value": "upper", "confidence": 0.9, "sample_count": 3, "agreement": 0.95},
                "alignment": {"value": "center", "confidence": 0.85, "sample_count": 3, "agreement": 0.9},
                "bold": {"value": True, "confidence": 0.9, "sample_count": 3, "agreement": 1.0},
            },
            {
                "level": 2,
                "case_style": {"value": "title", "confidence": 0.8, "sample_count": 3, "agreement": 0.85},
                "alignment": {"value": "left", "confidence": 0.9, "sample_count": 3, "agreement": 1.0},
                "bold": {"value": True, "confidence": 0.85, "sample_count": 3, "agreement": 0.9},
            },
        ],
        "sections": [
            {"id": "table_of_contents", "frequency": 0.95, "median_order": 1},
            {"id": "table_of_authorities", "frequency": 0.9, "median_order": 2},
            {"id": "argument", "frequency": 1.0, "median_order": 5},
            {"id": "conclusion", "frequency": 1.0, "median_order": 6},
        ],
    }


def _write_temp_json(data: dict) -> Path:
    f = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
    json.dump(data, f)
    f.close()
    return Path(f.name)


class TestLoadFormatSpec:
    def test_load_basic(self):
        path = _write_temp_json(_make_export_json())
        spec = load_format_spec(path)

        assert spec.document_count == 3
        assert spec.overall_confidence == 0.72
        assert spec.typography.font_family == "Times New Roman"
        assert spec.typography.font_size_pt == 13.0
        assert spec.typography.line_spacing == 2.0
        path.unlink()

    def test_load_layout(self):
        path = _write_temp_json(_make_export_json())
        spec = load_format_spec(path)

        assert spec.layout.margin_top == 1.0
        assert spec.layout.margin_left == 1.25
        path.unlink()

    def test_load_headings(self):
        path = _write_temp_json(_make_export_json())
        spec = load_format_spec(path)

        assert len(spec.headings) == 2
        assert spec.headings[0].level == 1
        assert spec.headings[0].case_style == "upper"
        assert spec.headings[1].level == 2
        assert spec.headings[1].case_style == "title"
        path.unlink()

    def test_load_sections(self):
        path = _write_temp_json(_make_export_json())
        spec = load_format_spec(path)

        assert len(spec.sections) == 4
        assert spec.sections[0].id == "table_of_contents"
        assert spec.sections[2].frequency == 1.0
        path.unlink()

    def test_no_content_in_spec(self):
        """Ensure no document content leaks into the format spec."""
        path = _write_temp_json(_make_export_json())
        spec = load_format_spec(path)

        # FormatSpec should have no fields that could carry content
        assert not hasattr(spec, "source_filename")
        assert not hasattr(spec, "author")
        assert not hasattr(spec, "case_name")
        path.unlink()


class TestMergeWithRules:
    def test_defaults_only(self):
        result = merge_with_rules(rules={})
        assert result["font_name"] == "Times New Roman"
        assert result["font_size_pt"] == 13.0
        assert result["_provenance"]["font_name"] == "default"

    def test_rules_override_defaults(self):
        rules = {"page_format": {"font_name": "Courier New", "font_size_pt": 12.0}}
        result = merge_with_rules(rules)

        assert result["font_name"] == "Courier New"
        assert result["font_size_pt"] == 12.0
        assert result["_provenance"]["font_name"] == "rule"
        assert result["_provenance"]["font_size_pt"] == "rule"

    def test_ml_overrides_defaults(self):
        path = _write_temp_json(_make_export_json())
        spec = load_format_spec(path)
        result = merge_with_rules(rules={}, ml_spec=spec)

        assert result["font_name"] == "Times New Roman"
        assert result["margin_left_inches"] == 1.25
        assert result["_provenance"]["margin_left_inches"] == "ml_learned"
        path.unlink()

    def test_rules_override_ml(self):
        """Mandatory rules always beat ML-learned patterns."""
        path = _write_temp_json(_make_export_json())
        spec = load_format_spec(path)
        rules = {"page_format": {"font_name": "Arial"}}
        result = merge_with_rules(rules, ml_spec=spec)

        # Rule wins over ML
        assert result["font_name"] == "Arial"
        assert result["_provenance"]["font_name"] == "rule"

        # ML still provides values where rules are silent
        assert result["margin_left_inches"] == 1.25
        assert result["_provenance"]["margin_left_inches"] == "ml_learned"
        path.unlink()

    def test_hierarchy_is_rules_ml_defaults(self):
        """Full 3-tier merge: defaults -> ML -> rules."""
        path = _write_temp_json(_make_export_json())
        spec = load_format_spec(path)
        rules = {"page_format": {"font_size_pt": 12.0}}
        result = merge_with_rules(rules, ml_spec=spec)

        # Rule wins for font_size_pt
        assert result["font_size_pt"] == 12.0
        assert result["_provenance"]["font_size_pt"] == "rule"

        # ML wins for font_name (rule silent)
        assert result["font_name"] == "Times New Roman"
        assert result["_provenance"]["font_name"] == "ml_learned"

        # Default wins for block_quote_indent (both rule and ML silent)
        assert result["block_quote_indent_inches"] == 0.5
        assert result["_provenance"]["block_quote_indent_inches"] == "default"
        path.unlink()
