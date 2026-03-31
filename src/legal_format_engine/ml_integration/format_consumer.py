"""Format consumer: loads ML-exported format specs and merges with rules.

This module consumes the format-only JSON exported by the ML engine's
format_export module. It applies the hierarchy:

    Mandatory Rules > ML-Learned Patterns > Defaults

No raw document content ever passes through this module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LearnedTypography:
    """Typography patterns learned from training documents."""
    font_family: str | None = None
    font_family_confidence: float = 0.0
    font_size_pt: float | None = None
    font_size_confidence: float = 0.0
    line_spacing: float | None = None
    line_spacing_confidence: float = 0.0


@dataclass
class LearnedLayout:
    """Layout patterns learned from training documents."""
    margin_top: float | None = None
    margin_bottom: float | None = None
    margin_left: float | None = None
    margin_right: float | None = None
    body_indent: float | None = None
    block_quote_indent: float | None = None


@dataclass
class LearnedHeading:
    """Heading style learned for a specific level."""
    level: int = 1
    case_style: str | None = None
    alignment: str | None = None
    bold: bool | None = None
    font_size_pt: float | None = None
    numbering: str | None = None


@dataclass
class LearnedSection:
    """Section presence and ordering pattern."""
    id: str = ""
    frequency: float = 0.0
    median_order: int = 0


@dataclass
class FormatSpec:
    """Complete format specification imported from the ML engine.

    Contains ONLY formatting metadata — never document content.
    """
    document_count: int = 0
    overall_confidence: float = 0.0
    typography: LearnedTypography = field(default_factory=LearnedTypography)
    layout: LearnedLayout = field(default_factory=LearnedLayout)
    headings: list[LearnedHeading] = field(default_factory=list)
    sections: list[LearnedSection] = field(default_factory=list)


def load_format_spec(path: str | Path) -> FormatSpec:
    """Load a format spec from a JSON file exported by the ML engine.

    Args:
        path: Path to the JSON file produced by
              anchor_ml_engine.format_export.export_learned_format()

    Returns:
        A FormatSpec containing only formatting patterns.
    """
    path = Path(path)
    with open(path) as f:
        data = json.load(f)

    spec = FormatSpec()

    # Metadata
    meta = data.get("_export_metadata", {})
    spec.document_count = meta.get("document_count", 0)
    spec.overall_confidence = meta.get("overall_confidence", 0.0)

    # Typography
    typo = data.get("typography", {})
    spec.typography = LearnedTypography(
        font_family=_val(typo, "font_family"),
        font_family_confidence=_conf(typo, "font_family"),
        font_size_pt=_val(typo, "font_size_pt"),
        font_size_confidence=_conf(typo, "font_size_pt"),
        line_spacing=_val(typo, "line_spacing"),
        line_spacing_confidence=_conf(typo, "line_spacing"),
    )

    # Layout
    layout_data = data.get("layout", {})
    spec.layout = LearnedLayout(
        margin_top=_val(layout_data, "margin_top"),
        margin_bottom=_val(layout_data, "margin_bottom"),
        margin_left=_val(layout_data, "margin_left"),
        margin_right=_val(layout_data, "margin_right"),
        body_indent=_val(layout_data, "body_indent"),
        block_quote_indent=_val(layout_data, "block_quote_indent"),
    )

    # Headings
    for h in data.get("headings", []):
        spec.headings.append(LearnedHeading(
            level=h.get("level", 1),
            case_style=_val(h, "case_style"),
            alignment=_val(h, "alignment"),
            bold=_val(h, "bold"),
            font_size_pt=_val(h, "font_size_pt"),
            numbering=_val(h, "numbering"),
        ))

    # Sections
    for s in data.get("sections", []):
        spec.sections.append(LearnedSection(
            id=s.get("id", ""),
            frequency=s.get("frequency", 0.0),
            median_order=s.get("median_order", 0),
        ))

    return spec


def merge_with_rules(
    rules: dict,
    ml_spec: FormatSpec | None = None,
    defaults: dict | None = None,
) -> dict:
    """Merge mandatory rules with ML-learned patterns and defaults.

    Hierarchy: Rules > ML-Learned > Defaults

    Args:
        rules: Mandatory formatting rules (always win).
        ml_spec: Optional ML-learned format spec.
        defaults: Optional default values.

    Returns:
        A merged formatting dict with provenance annotations.
    """
    defaults = defaults or _get_defaults()
    result: dict = {"_provenance": {}}

    # Start with defaults
    for key, value in defaults.items():
        result[key] = value
        result["_provenance"][key] = "default"

    # Layer ML-learned patterns on top (only if confident enough)
    if ml_spec and ml_spec.overall_confidence > 0:
        _apply_ml_typography(result, ml_spec.typography)
        _apply_ml_layout(result, ml_spec.layout)

    # Mandatory rules always win
    page_format = rules.get("page_format", {})
    for key, value in page_format.items():
        result[key] = value
        result["_provenance"][key] = "rule"

    return result


# -- Minimum confidence to apply an ML-learned value --
_MIN_ML_CONFIDENCE = 0.3


def _apply_ml_typography(result: dict, typo: LearnedTypography) -> None:
    if typo.font_family and typo.font_family_confidence >= _MIN_ML_CONFIDENCE:
        result["font_name"] = typo.font_family
        result["_provenance"]["font_name"] = "ml_learned"
    if typo.font_size_pt and typo.font_size_confidence >= _MIN_ML_CONFIDENCE:
        result["font_size_pt"] = typo.font_size_pt
        result["_provenance"]["font_size_pt"] = "ml_learned"
    if typo.line_spacing and typo.line_spacing_confidence >= _MIN_ML_CONFIDENCE:
        result["line_spacing"] = typo.line_spacing
        result["_provenance"]["line_spacing"] = "ml_learned"


def _apply_ml_layout(result: dict, layout: LearnedLayout) -> None:
    field_map = {
        "margin_top": "margin_top_inches",
        "margin_bottom": "margin_bottom_inches",
        "margin_left": "margin_left_inches",
        "margin_right": "margin_right_inches",
        "body_indent": "body_first_line_indent_inches",
        "block_quote_indent": "block_quote_indent_inches",
    }
    for attr, key in field_map.items():
        val = getattr(layout, attr, None)
        if val is not None:
            result[key] = val
            result["_provenance"][key] = "ml_learned"


def _val(section: dict, key: str) -> object | None:
    entry = section.get(key)
    if isinstance(entry, dict):
        return entry.get("value")
    return None


def _conf(section: dict, key: str) -> float:
    entry = section.get(key)
    if isinstance(entry, dict):
        return entry.get("confidence", 0.0)
    return 0.0


def _get_defaults() -> dict:
    """Sensible defaults for legal document formatting."""
    return {
        "font_name": "Times New Roman",
        "font_size_pt": 13.0,
        "line_spacing": 2.0,
        "margin_top_inches": 1.0,
        "margin_bottom_inches": 1.0,
        "margin_left_inches": 1.0,
        "margin_right_inches": 1.0,
        "body_first_line_indent_inches": 0.5,
        "block_quote_indent_inches": 0.5,
        "page_width_inches": 8.5,
        "page_height_inches": 11.0,
    }
