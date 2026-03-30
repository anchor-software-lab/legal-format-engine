"""Rule hierarchy: court rules ALWAYS win over ML-learned patterns.

This is the gatekeeper between the ML system and the formatting engine.
It enforces a strict hierarchy:

    1. COURT RULES (YAML rulesets) — mandatory, never overridden
    2. ML-LEARNED PATTERNS — consensus from uploaded documents
    3. STYLE PROFILES (author/firm) — discretionary preferences
    4. ENGINE DEFAULTS — fallback for anything not specified

When a court rule specifies a value (e.g., "font_size_pt: 12"), no amount
of ML evidence can override it. If 100 uploaded briefs use 13pt font but
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

from dataclasses import dataclass, field
from typing import Any

from legal_format_engine.ml.learner import LearnedFormat
from legal_format_engine.ml.styles import StyleProfile
from legal_format_engine.rules.schema import Ruleset


@dataclass
class FormattingDecision:
    """A single formatting decision with full provenance."""
    field: str  # e.g., "page_format.font_size_pt"
    value: Any  # the decided value
    source: str  # "rule", "ml_learned", "style_profile", "default"
    confidence: float = 1.0  # 1.0 for rules, varies for ML/style
    explanation: str = ""


@dataclass
class ResolvedFormat:
    """Complete formatting specification with provenance for every decision.

    Every formatting field has a value and a clear source explaining
    where it came from. This is what the engine uses to format documents.
    """
    jurisdiction: str
    court_level: str
    document_type: str

    decisions: list[FormattingDecision] = field(default_factory=list)

    # Convenience: count by source
    @property
    def rule_count(self) -> int:
        return sum(1 for d in self.decisions if d.source == "rule")

    @property
    def ml_count(self) -> int:
        return sum(1 for d in self.decisions if d.source == "ml_learned")

    @property
    def style_count(self) -> int:
        return sum(1 for d in self.decisions if d.source == "style_profile")

    @property
    def default_count(self) -> int:
        return sum(1 for d in self.decisions if d.source == "default")

    def get(self, field_name: str) -> FormattingDecision | None:
        for d in self.decisions:
            if d.field == field_name:
                return d
        return None

    def to_dict(self) -> dict:
        return {
            "jurisdiction": self.jurisdiction,
            "court_level": self.court_level,
            "document_type": self.document_type,
            "decisions": [
                {
                    "field": d.field,
                    "value": d.value,
                    "source": d.source,
                    "confidence": d.confidence,
                    "explanation": d.explanation,
                }
                for d in self.decisions
            ],
            "summary": {
                "total": len(self.decisions),
                "from_rules": self.rule_count,
                "from_ml": self.ml_count,
                "from_style": self.style_count,
                "from_defaults": self.default_count,
            },
        }


# Fields that are ALWAYS governed by court rules when present in the YAML.
# If the ruleset specifies these, the value is law. No ML override.
RULE_GOVERNED_FIELDS = {
    # Page format — courts specify these
    "font_name",
    "font_size_pt",
    "line_spacing",
    "margin_top_inches",
    "margin_bottom_inches",
    "margin_left_inches",
    "margin_right_inches",
    "page_width_inches",
    "page_height_inches",

    # Heading rules — courts often specify level formatting
    "heading_case_style",
    "heading_alignment",
    "heading_numbering",
    "heading_bold",

    # Required sections — courts mandate what must be included
    "required_sections",
    "section_order",

    # Caption formatting — courts specify this
    "caption_court_line_style",
    "caption_case_number_prefix",
    "caption_party_separator",
    "caption_party_name_style",

    # Certifications — specific legal language required
    "certifications",
}


def identify_rule_governed_fields(ruleset: Ruleset) -> set[str]:
    """Identify which fields are explicitly specified by the court ruleset.

    A field is rule-governed if the ruleset provides a non-default value
    for it. Fields where the ruleset is silent are discretionary.
    """
    governed = set()

    pf = ruleset.page_format

    # Check each page format field against defaults
    defaults = {
        "font_name": "Times New Roman",
        "font_size_pt": 12,
        "line_spacing": 2.0,
        "margin_top_inches": 1.0,
        "margin_bottom_inches": 1.0,
        "margin_left_inches": 1.0,
        "margin_right_inches": 1.0,
    }

    # If the ruleset specifies ANY value for these (even the default),
    # treat them as rule-governed. The YAML files we wrote explicitly
    # set these values, so they're intentional.
    governed.add("font_name")
    governed.add("font_size_pt")
    governed.add("line_spacing")
    governed.add("margin_top_inches")
    governed.add("margin_bottom_inches")
    governed.add("margin_left_inches")
    governed.add("margin_right_inches")

    # Heading rules: governed at the level they're defined
    for hr in ruleset.heading_rules:
        governed.add(f"heading_{hr.level}_case_style")
        governed.add(f"heading_{hr.level}_alignment")
        governed.add(f"heading_{hr.level}_bold")
        if hr.numbering is not None:
            governed.add(f"heading_{hr.level}_numbering")

    # Required sections
    if ruleset.required_sections:
        governed.add("required_sections")
        governed.add("section_order")

    # Caption
    governed.add("caption_style")

    # Certifications
    if ruleset.certifications:
        governed.add("certifications")

    return governed


def resolve_format(
    ruleset: Ruleset,
    learned: LearnedFormat | None = None,
    style: StyleProfile | None = None,
) -> ResolvedFormat:
    """Resolve final formatting by applying the hierarchy:

    Rule > ML Learned > Style Profile > Default

    Every decision is tracked with provenance.
    """
    resolved = ResolvedFormat(
        jurisdiction=ruleset.jurisdiction,
        court_level=ruleset.court_level,
        document_type=ruleset.document_type,
    )

    governed = identify_rule_governed_fields(ruleset)
    pf = ruleset.page_format

    # ------- TYPOGRAPHY -------

    # Font name: ALWAYS from rule
    resolved.decisions.append(FormattingDecision(
        field="font_name",
        value=pf.font_name,
        source="rule",
        confidence=1.0,
        explanation=f"Court rule requires {pf.font_name}",
    ))

    # Font size: ALWAYS from rule
    resolved.decisions.append(FormattingDecision(
        field="font_size_pt",
        value=pf.font_size_pt,
        source="rule",
        confidence=1.0,
        explanation=f"Court rule requires {pf.font_size_pt}pt",
    ))

    # Line spacing: ALWAYS from rule
    resolved.decisions.append(FormattingDecision(
        field="line_spacing",
        value=pf.line_spacing,
        source="rule",
        confidence=1.0,
        explanation=f"Court rule requires {pf.line_spacing}x spacing",
    ))

    # ------- MARGINS -------

    for margin_field in ("margin_top_inches", "margin_bottom_inches",
                         "margin_left_inches", "margin_right_inches"):
        val = getattr(pf, margin_field)
        resolved.decisions.append(FormattingDecision(
            field=margin_field,
            value=val,
            source="rule",
            confidence=1.0,
            explanation=f"Court rule requires {val}\" {margin_field.split('_')[1]} margin",
        ))

    # ------- HEADINGS -------

    for hr in ruleset.heading_rules:
        lvl = hr.level

        resolved.decisions.append(FormattingDecision(
            field=f"heading_{lvl}_case_style",
            value=hr.case_style,
            source="rule",
            confidence=1.0,
            explanation=f"Court rule: level {lvl} headings use {hr.case_style} case",
        ))

        resolved.decisions.append(FormattingDecision(
            field=f"heading_{lvl}_alignment",
            value=hr.alignment,
            source="rule",
            confidence=1.0,
            explanation=f"Court rule: level {lvl} headings are {hr.alignment}-aligned",
        ))

        resolved.decisions.append(FormattingDecision(
            field=f"heading_{lvl}_bold",
            value=hr.bold,
            source="rule",
            confidence=1.0,
            explanation=f"Court rule: level {lvl} headings {'bold' if hr.bold else 'not bold'}",
        ))

        if hr.numbering is not None:
            resolved.decisions.append(FormattingDecision(
                field=f"heading_{lvl}_numbering",
                value=hr.numbering,
                source="rule",
                confidence=1.0,
                explanation=f"Court rule: level {lvl} numbering is {hr.numbering}",
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
                    f"Author/firm preference from {pref.sample_count} documents "
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

    # No learned data — use conventional defaults
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
