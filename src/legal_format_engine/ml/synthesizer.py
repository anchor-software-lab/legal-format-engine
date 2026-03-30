"""ML Synthesizer - generates YAML rulesets from learned patterns and diffs against existing."""

from __future__ import annotations
from typing import Optional

import yaml

from legal_format_engine.ml.learner import LearnedPatterns
from legal_format_engine.rules.base import load_ruleset


def synthesize_ruleset(patterns: LearnedPatterns, name: str = "ML Generated") -> str:
    """Generate a YAML ruleset from learned patterns."""
    ruleset = {
        "name": name,
        "jurisdiction": patterns.jurisdiction or "unknown",
        "court_level": "court_of_appeals",
        "document_type": "appellate_brief",
        "description": f"Auto-generated from {patterns.document_count} documents",
        "page_format": {},
    }

    pf = ruleset["page_format"]
    if patterns.font_name:
        pf["font"] = patterns.font_name
    if patterns.font_size_pt is not None:
        pf["font_size_pt"] = patterns.font_size_pt
    if patterns.line_spacing is not None:
        pf["line_spacing"] = "double" if patterns.line_spacing >= 1.8 else "single"
    if patterns.margin_top is not None:
        pf["margin_top_inches"] = patterns.margin_top
    if patterns.margin_bottom is not None:
        pf["margin_bottom_inches"] = patterns.margin_bottom
    if patterns.margin_left is not None:
        pf["margin_left_inches"] = patterns.margin_left
    if patterns.margin_right is not None:
        pf["margin_right_inches"] = patterns.margin_right
    if patterns.first_line_indent is not None:
        pf["first_line_indent_inches"] = patterns.first_line_indent

    return yaml.dump(ruleset, default_flow_style=False, sort_keys=False)


def recommend_changes(
    patterns: LearnedPatterns,
    jurisdiction: str = "wisconsin",
    document_type: str = "appellate_brief",
) -> list[dict]:
    """Compare ML patterns against existing ruleset and recommend changes.

    Returns a list of recommendations with confidence scores.
    Only recommends changes for discretionary fields (not court-mandated ones).
    """
    try:
        existing = load_ruleset(jurisdiction, document_type)
    except FileNotFoundError:
        return [{"field": "ruleset", "message": f"No ruleset found for {jurisdiction}/{document_type}"}]

    recommendations = []
    pf = existing.page_format

    # Court-mandated fields (don't recommend changes)
    mandated = {"font", "font_size_pt", "margin_top_inches", "margin_bottom_inches",
                "margin_left_inches", "margin_right_inches", "line_spacing"}

    # Discretionary fields (OK to recommend)
    if patterns.first_line_indent is not None:
        current = pf.first_line_indent_inches
        if patterns.first_line_indent != current:
            recommendations.append({
                "field": "first_line_indent_inches",
                "current": current,
                "suggested": patterns.first_line_indent,
                "confidence": 0.7,
                "reason": f"ML learned {patterns.first_line_indent}\" from {patterns.document_count} documents",
                "is_discretionary": True,
            })

    # Font comparison (informational only)
    if patterns.font_name and patterns.font_name != pf.font:
        recommendations.append({
            "field": "font",
            "current": pf.font,
            "suggested": patterns.font_name,
            "confidence": patterns.font_name_confidence,
            "reason": f"ML detected {patterns.font_name} in {patterns.document_count} documents",
            "is_discretionary": False,
            "note": "Court rule governs this field",
        })

    # Font size comparison (informational only)
    if patterns.font_size_pt is not None and patterns.font_size_pt != pf.font_size_pt:
        recommendations.append({
            "field": "font_size_pt",
            "current": pf.font_size_pt,
            "suggested": patterns.font_size_pt,
            "confidence": patterns.font_size_confidence,
            "reason": f"ML detected {patterns.font_size_pt}pt in {patterns.document_count} documents",
            "is_discretionary": False,
            "note": "Court rule governs this field",
        })

    return recommendations
