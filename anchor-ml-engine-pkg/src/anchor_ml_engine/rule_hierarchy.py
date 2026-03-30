"""Rule hierarchy: mandatory rules ALWAYS win over ML-learned patterns.

This is the gatekeeper between the ML system and the formatting engine.
It enforces a strict hierarchy:

    1. MANDATORY RULES (rulesets) -- never overridden
    2. ML-LEARNED PATTERNS -- consensus from uploaded documents
    3. STYLE PROFILES (author/organization) -- discretionary preferences
    4. ENGINE DEFAULTS -- fallback for anything not specified

When a rule specifies a value (e.g., "font_size_pt: 12"), no amount
of ML evidence can override it. If 100 uploaded documents use 13pt font but
the rule says 12pt, the output is 12pt. Period.

When the rule is SILENT on a field (e.g., first-line indent, block quote
formatting), the ML and style profiles fill in with learned values.

This module:
- Identifies which formatting fields are rule-governed vs. discretionary
- Filters ML recommendations to only apply to discretionary areas
- Merges rule + ML + style profile into a final formatting spec
- Provides clear provenance for every formatting decision
"""

from __future__ import annotations

from typing import Any

from anchor_ml_engine.models import (
    FormattingDecision,
    LearnedFormat,
    ResolvedFormat,
    StyleProfile,
)


# Fields that are ALWAYS governed by rules when present.
# If the ruleset specifies these, the value is law. No ML override.
RULE_GOVERNED_FIELDS = {
    # Page format -- rules specify these
    "font_name",
    "font_size_pt",
    "line_spacing",
    "margin_top_inches",
    "margin_bottom_inches",
    "margin_left_inches",
    "margin_right_inches",
    "page_width_inches",
    "page_height_inches",

    # Heading rules -- rules often specify level formatting
    "heading_case_style",
    "heading_alignment",
    "heading_numbering",
    "heading_bold",

    # Required sections -- rules mandate what must be included
    "required_sections",
    "section_order",

    # Caption formatting
    "caption_court_line_style",
    "caption_case_number_prefix",
    "caption_party_separator",
    "caption_party_name_style",

    # Certifications -- specific language required
    "certifications",
}


def identify_rule_governed_fields(rules: dict) -> set[str]:
    """Identify which fields are explicitly specified by the rules dict.

    A field is rule-governed if the rules dict provides a value for it.
    Fields where the rules are silent are discretionary.

    Args:
        rules: A dict containing mandatory formatting rules.

    Returns:
        Set of field names that are governed by the rules.
    """
    governed = set()

    page_format = rules.get("page_format", {})

    # If the rules specify any page format fields, they're governed
    for key in ("font_name", "font_size_pt", "line_spacing",
                "margin_top_inches", "margin_bottom_inches",
                "margin_left_inches", "margin_right_inches"):
        if key in page_format:
            governed.add(key)

    # Heading rules
    for hr in rules.get("heading_rules", []):
        level = hr.get("level", 0)
        if "case_style" in hr:
            governed.add(f"heading_{level}_case_style")
        if "alignment" in hr:
            governed.add(f"heading_{level}_alignment")
        if "bold" in hr:
            governed.add(f"heading_{level}_bold")
        if "numbering" in hr and hr["numbering"] is not None:
            governed.add(f"heading_{level}_numbering")

    # Required sections
    if rules.get("required_sections"):
        governed.add("required_sections")
        governed.add("section_order")

    return governed


def resolve_format(
    rules: dict,
    learned: LearnedFormat | None = None,
    style: StyleProfile | None = None,
) -> ResolvedFormat:
    """Resolve final formatting by applying the hierarchy:

    Rule > ML Learned > Style Profile > Default

    Every decision is tracked with provenance.

    Args:
        rules: Mandatory rules dict with page_format, heading_rules, etc.
        learned: Optional ML-learned format patterns.
        style: Optional per-author/organization style profile.

    Returns:
        ResolvedFormat with all decisions and their provenance.
    """
    resolved = ResolvedFormat(
        category=rules.get("category", ""),
        subcategory=rules.get("subcategory", ""),
        document_type=rules.get("document_type", ""),
    )

    governed = identify_rule_governed_fields(rules)
    pf = rules.get("page_format", {})

    # ------- TYPOGRAPHY -------

    if "font_name" in pf:
        resolved.decisions.append(FormattingDecision(
            field="font_name",
            value=pf["font_name"],
            source="rule",
            confidence=1.0,
            explanation=f"Rule requires {pf['font_name']}",
        ))

    if "font_size_pt" in pf:
        resolved.decisions.append(FormattingDecision(
            field="font_size_pt",
            value=pf["font_size_pt"],
            source="rule",
            confidence=1.0,
            explanation=f"Rule requires {pf['font_size_pt']}pt",
        ))

    if "line_spacing" in pf:
        resolved.decisions.append(FormattingDecision(
            field="line_spacing",
            value=pf["line_spacing"],
            source="rule",
            confidence=1.0,
            explanation=f"Rule requires {pf['line_spacing']}x spacing",
        ))

    # ------- MARGINS -------

    for margin_field in ("margin_top_inches", "margin_bottom_inches",
                         "margin_left_inches", "margin_right_inches"):
        if margin_field in pf:
            val = pf[margin_field]
            resolved.decisions.append(FormattingDecision(
                field=margin_field,
                value=val,
                source="rule",
                confidence=1.0,
                explanation=f"Rule requires {val}\" {margin_field.split('_')[1]} margin",
            ))

    # ------- HEADINGS -------

    for hr in rules.get("heading_rules", []):
        lvl = hr.get("level", 0)

        if "case_style" in hr:
            resolved.decisions.append(FormattingDecision(
                field=f"heading_{lvl}_case_style",
                value=hr["case_style"],
                source="rule",
                confidence=1.0,
                explanation=f"Rule: level {lvl} headings use {hr['case_style']} case",
            ))

        if "alignment" in hr:
            resolved.decisions.append(FormattingDecision(
                field=f"heading_{lvl}_alignment",
                value=hr["alignment"],
                source="rule",
                confidence=1.0,
                explanation=f"Rule: level {lvl} headings are {hr['alignment']}-aligned",
            ))

        if "bold" in hr:
            resolved.decisions.append(FormattingDecision(
                field=f"heading_{lvl}_bold",
                value=hr["bold"],
                source="rule",
                confidence=1.0,
                explanation=f"Rule: level {lvl} headings {'bold' if hr['bold'] else 'not bold'}",
            ))

        if "numbering" in hr and hr["numbering"] is not None:
            resolved.decisions.append(FormattingDecision(
                field=f"heading_{lvl}_numbering",
                value=hr["numbering"],
                source="rule",
                confidence=1.0,
                explanation=f"Rule: level {lvl} numbering is {hr['numbering']}",
            ))

    # ------- DISCRETIONARY FIELDS (ML + Style fill the gaps) -------

    # Body paragraph first-line indent (rules almost never specify this)
    _resolve_discretionary(
        resolved, "body_first_line_indent",
        learned_attr="body_indent",
        learned_format=learned,
        style=style,
        default=0.5,
        unit="inches",
    )

    # Block quote indent
    _resolve_discretionary(
        resolved, "block_quote_indent",
        learned_attr="block_quote_indent",
        learned_format=learned,
        style=style,
        default=0.5,
        unit="inches",
    )

    # Heading spacing (discretionary)
    _resolve_discretionary(
        resolved, "heading_space_before_pt",
        learned_attr=None,
        learned_format=None,
        style=style,
        default=12.0,
        unit="pt",
    )
    _resolve_discretionary(
        resolved, "heading_space_after_pt",
        learned_attr=None,
        learned_format=None,
        style=style,
        default=6.0,
        unit="pt",
    )

    # Heading numbering for levels where rule is silent
    for level in (1, 2, 3, 4):
        numbering_field = f"heading_{level}_numbering"
        if numbering_field not in governed:
            _resolve_discretionary_heading_numbering(
                resolved, level, learned, style,
            )

    return resolved


def _resolve_discretionary(
    resolved: ResolvedFormat,
    field_name: str,
    learned_attr: str | None,
    learned_format: LearnedFormat | None,
    style: StyleProfile | None,
    default: Any,
    unit: str = "",
) -> None:
    """Resolve a discretionary field through the hierarchy: ML > Style > Default."""

    # Try ML learned value first
    if learned_format and learned_attr:
        learned_val = getattr(learned_format, learned_attr, None)
        if learned_val is not None and learned_val.confidence >= 0.3:
            resolved.decisions.append(FormattingDecision(
                field=field_name,
                value=learned_val.value,
                source="ml_learned",
                confidence=learned_val.confidence,
                explanation=(
                    f"Learned from {learned_val.sample_count} documents "
                    f"({learned_val.agreement:.0%} agreement)"
                ),
            ))
            return

    # Try style profile
    if style:
        pref = style.get(field_name)
        if pref is not None and pref.consistency >= 0.5:
            resolved.decisions.append(FormattingDecision(
                field=field_name,
                value=pref.value,
                source="style_profile",
                confidence=pref.consistency,
                explanation=(
                    f"Author/org preference from {pref.sample_count} documents "
                    f"({pref.consistency:.0%} consistent)"
                ),
            ))
            return

    # Fall back to default
    unit_str = f"{unit} " if unit else ""
    resolved.decisions.append(FormattingDecision(
        field=field_name,
        value=default,
        source="default",
        confidence=0.5,
        explanation=f"Engine default: {default}{unit_str}(rule silent, no ML data)",
    ))


def _resolve_discretionary_heading_numbering(
    resolved: ResolvedFormat,
    level: int,
    learned: LearnedFormat | None,
    style: StyleProfile | None,
) -> None:
    """Resolve heading numbering when the rule doesn't specify it."""
    field_name = f"heading_{level}_numbering"

    # Check ML learned heading styles
    if learned:
        for hs in learned.heading_styles:
            if hs.level == level and hs.numbering and hs.numbering.confidence >= 0.3:
                resolved.decisions.append(FormattingDecision(
                    field=field_name,
                    value=hs.numbering.value,
                    source="ml_learned",
                    confidence=hs.numbering.confidence,
                    explanation=(
                        f"Learned from documents: level {level} headings "
                        f"typically use {hs.numbering.value} numbering"
                    ),
                ))
                return

    # No learned data -- use conventional defaults
    level_defaults = {
        1: None,
        2: "roman",
        3: "alpha_upper",
        4: "arabic",
    }
    resolved.decisions.append(FormattingDecision(
        field=field_name,
        value=level_defaults.get(level),
        source="default",
        confidence=0.5,
        explanation=f"Engine default numbering for level {level}",
    ))
