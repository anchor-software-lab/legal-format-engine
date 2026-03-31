"""Tests for the content consumer — structural pattern integration."""

import json
import tempfile
from pathlib import Path

from legal_format_engine.ml_integration.content_consumer import (
    DocumentStructureSpec,
    load_structure_spec,
    suggest_argument_outline,
)


def _make_structure_export() -> dict:
    """Simulates what the ML engine's export_argument_structure() produces."""
    return {
        "_export_metadata": {
            "exported_at": "2026-03-30T20:00:00Z",
            "engine_version": "0.1.0",
            "document_type": "brief_in_chief",
            "governance": "structural export — distilled patterns only, no verbatim content",
        },
        "document_metrics": {
            "total_word_count": 8500,
            "total_page_count": 0,
            "total_sections": 8,
            "total_arguments": 3,
            "argument_to_total_ratio": 0.65,
        },
        "argument_sections": [
            {
                "id": "section_1",
                "section_type": "standard_of_review",
                "argument_type": "",
                "standard_of_review": "abuse_of_discretion",
                "reasoning_flow": ["standard_of_review", "rule_statement"],
                "citation_count": 3,
                "word_count": 200,
                "depth": 1,
            },
            {
                "id": "section_2",
                "section_type": "main_argument",
                "argument_type": "expert_testimony",
                "standard_of_review": "abuse_of_discretion",
                "reasoning_flow": [
                    "rule_statement", "rule_explanation",
                    "fact_application", "conclusion",
                ],
                "citation_count": 8,
                "word_count": 1500,
                "depth": 1,
            },
            {
                "id": "section_3",
                "section_type": "sub_argument",
                "argument_type": "harmless_error",
                "standard_of_review": "",
                "reasoning_flow": ["rule_statement", "fact_application", "conclusion"],
                "citation_count": 3,
                "word_count": 600,
                "depth": 2,
            },
        ],
        "citation_graph": {
            "total_citations": 14,
            "unique_authorities": 8,
            "citation_density": 4.1,
            "by_section": {"argument": 11, "standard_of_review": 3},
            "signal_distribution": {"none": 8, "see": 3, "see also": 2, "cf.": 1},
            "court_distribution": {"Wis.": 10, "SCOTUS": 2, "Federal": 2},
            "pinpoint_rate": 0.714,
        },
        "reasoning_patterns": [
            {
                "pattern_type": "rule_application",
                "components": [
                    "rule_statement", "rule_explanation",
                    "fact_application", "conclusion",
                ],
                "frequency": 0.667,
                "typical_citation_density": 3.5,
            },
            {
                "pattern_type": "deductive",
                "components": ["rule_statement", "fact_application", "conclusion"],
                "frequency": 0.333,
                "typical_citation_density": 2.0,
            },
        ],
    }


def _write_temp_json(data: dict) -> Path:
    f = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
    json.dump(data, f)
    f.close()
    return Path(f.name)


class TestLoadStructureSpec:
    def test_load_basic(self):
        path = _write_temp_json(_make_structure_export())
        spec = load_structure_spec(path)

        assert spec.document_type == "brief_in_chief"
        assert spec.total_word_count == 8500
        assert spec.total_arguments == 3
        path.unlink()

    def test_load_sections(self):
        path = _write_temp_json(_make_structure_export())
        spec = load_structure_spec(path)

        assert len(spec.sections) == 3
        assert spec.sections[0].section_type == "standard_of_review"
        assert spec.sections[1].argument_type == "expert_testimony"
        assert spec.sections[1].reasoning_flow == [
            "rule_statement", "rule_explanation",
            "fact_application", "conclusion",
        ]
        path.unlink()

    def test_load_citation_patterns(self):
        path = _write_temp_json(_make_structure_export())
        spec = load_structure_spec(path)

        cp = spec.citation_patterns
        assert cp.total_citations == 14
        assert cp.unique_authorities == 8
        assert cp.citation_density == 4.1
        assert cp.pinpoint_rate == 0.714
        assert cp.court_distribution["Wis."] == 10
        path.unlink()

    def test_load_reasoning_models(self):
        path = _write_temp_json(_make_structure_export())
        spec = load_structure_spec(path)

        assert len(spec.reasoning_models) == 2
        assert spec.reasoning_models[0].pattern_type == "rule_application"
        assert spec.reasoning_models[0].frequency == 0.667
        path.unlink()

    def test_no_verbatim_content(self):
        path = _write_temp_json(_make_structure_export())
        spec = load_structure_spec(path)

        # DocumentStructureSpec should have no fields for raw text
        assert not hasattr(spec, "text")
        assert not hasattr(spec, "content")
        for section in spec.sections:
            assert not hasattr(section, "text")
        path.unlink()


class TestSuggestArgumentOutline:
    def test_suggest_basic(self):
        path = _write_temp_json(_make_structure_export())
        spec = load_structure_spec(path)
        outline = suggest_argument_outline(spec)

        assert len(outline) > 0
        # Should use the most frequent reasoning pattern
        components = [item["component"] for item in outline]
        assert "rule_statement" in components
        assert "conclusion" in components
        path.unlink()

    def test_suggest_by_argument_type(self):
        path = _write_temp_json(_make_structure_export())
        spec = load_structure_spec(path)
        outline = suggest_argument_outline(spec, argument_type="expert_testimony")

        assert len(outline) > 0
        path.unlink()

    def test_outline_has_descriptions(self):
        path = _write_temp_json(_make_structure_export())
        spec = load_structure_spec(path)
        outline = suggest_argument_outline(spec)

        for item in outline:
            assert "description" in item
            assert len(item["description"]) > 0
        path.unlink()
