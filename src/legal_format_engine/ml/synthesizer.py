"""Synthesizer: converts LearnedFormat into actionable formatting specs.

The synthesizer is the final stage of the ML pipeline. It takes the learned
patterns and produces:
1. A YAML-compatible ruleset dict that can be loaded by the engine
2. A diff against the existing YAML ruleset showing what the ML would change
3. User-facing recommendations with confidence levels

The key principle: the synthesizer NEVER silently overrides court rules.
It produces suggestions that a human (or the engine with user approval) can
apply. Court rules are the floor — ML can refine within them but not violate.
"""

from __future__ import annotations

from legal_format_engine.ml.learner import LearnedFormat, LearnedValue


# Minimum confidence to include a learned value in the synthesized output
_MIN_CONFIDENCE = 0.3

# Minimum confidence to recommend overriding an existing ruleset value
_OVERRIDE_CONFIDENCE = 0.7


def synthesize_ruleset(
    learned: LearnedFormat,
    jurisdiction: str | None = None,
    court_level: str = "appellate",
    document_type: str = "brief",
) -> dict:
    """Generate a YAML-compatible ruleset dict from learned patterns.

    Returns a dict matching the Ruleset schema structure that can be
    written to YAML or loaded directly.
    """
    jurisdiction = jurisdiction or learned.jurisdiction or "learned"
    court_level = court_level or learned.court_level or "appellate"
    document_type = document_type or learned.document_type or "brief"

    ruleset: dict = {
        "jurisdiction": jurisdiction,
        "court_level": court_level,
        "document_type": document_type,
        "_ml_metadata": {
            "document_count": learned.document_count,
            "overall_confidence": learned.overall_confidence,
        },
    }

    # Page format
    page_format: dict = {}
    if learned.font_family and learned.font_family.confidence >= _MIN_CONFIDENCE:
        page_format["font_name"] = learned.font_family.value
    if learned.font_size_pt and learned.font_size_pt.confidence >= _MIN_CONFIDENCE:
        page_format["font_size_pt"] = learned.font_size_pt.value
    if learned.line_spacing and learned.line_spacing.confidence >= _MIN_CONFIDENCE:
        page_format["line_spacing"] = learned.line_spacing.value
    if learned.margin_top and learned.margin_top.confidence >= _MIN_CONFIDENCE:
        page_format["margin_top_inches"] = learned.margin_top.value
    if learned.margin_bottom and learned.margin_bottom.confidence >= _MIN_CONFIDENCE:
        page_format["margin_bottom_inches"] = learned.margin_bottom.value
    if learned.margin_left and learned.margin_left.confidence >= _MIN_CONFIDENCE:
        page_format["margin_left_inches"] = learned.margin_left.value
    if learned.margin_right and learned.margin_right.confidence >= _MIN_CONFIDENCE:
        page_format["margin_right_inches"] = learned.margin_right.value

    page_format["page_width_inches"] = 8.5
    page_format["page_height_inches"] = 11.0

    if page_format:
        ruleset["page_format"] = page_format

    # Heading rules
    heading_rules = []
    for style in learned.heading_styles:
        rule: dict = {"level": style.level}

        if style.case_style and style.case_style.confidence >= _MIN_CONFIDENCE:
            rule["case_style"] = style.case_style.value
        else:
            rule["case_style"] = "title"  # safe default

        if style.alignment and style.alignment.confidence >= _MIN_CONFIDENCE:
            rule["alignment"] = style.alignment.value
        else:
            rule["alignment"] = "left"

        if style.bold and style.bold.confidence >= _MIN_CONFIDENCE:
            rule["bold"] = style.bold.value in ("1.0", "True", True, 1.0, "true")
        else:
            rule["bold"] = True

        if style.numbering and style.numbering.confidence >= _MIN_CONFIDENCE:
            rule["numbering"] = style.numbering.value
        else:
            rule["numbering"] = None

        heading_rules.append(rule)

    if heading_rules:
        ruleset["heading_rules"] = heading_rules

    # Section order (as required_sections skeleton)
    required_sections = []
    for i, section in enumerate(learned.section_order):
        if section.frequency < 0.3:
            continue  # skip rare sections

        sec: dict = {
            "id": section.id,
            "canonical_name": _section_id_to_name(section.id),
            "order": i + 1,
            "required": section.frequency >= 0.7,
            "heading_level": 1,
        }
        required_sections.append(sec)

    if required_sections:
        ruleset["required_sections"] = required_sections

    return ruleset


def diff_against_ruleset(
    learned: LearnedFormat,
    existing: dict,
) -> list[FormatRecommendation]:
    """Compare learned patterns against an existing ruleset.

    Returns a list of recommendations where the ML suggests changes,
    each with a confidence level and explanation.
    """
    recommendations: list[FormatRecommendation] = []
    existing_pf = existing.get("page_format", {})

    # Font family
    if learned.font_family and learned.font_family.confidence >= _OVERRIDE_CONFIDENCE:
        existing_font = existing_pf.get("font_name")
        if existing_font and existing_font != learned.font_family.value:
            recommendations.append(FormatRecommendation(
                field="page_format.font_name",
                current_value=existing_font,
                suggested_value=learned.font_family.value,
                confidence=learned.font_family.confidence,
                reason=f"Learned from {learned.font_family.sample_count} documents: "
                       f"{learned.font_family.agreement:.0%} use {learned.font_family.value}",
            ))

    # Font size
    if learned.font_size_pt and learned.font_size_pt.confidence >= _OVERRIDE_CONFIDENCE:
        existing_size = existing_pf.get("font_size_pt")
        if existing_size and existing_size != learned.font_size_pt.value:
            recommendations.append(FormatRecommendation(
                field="page_format.font_size_pt",
                current_value=existing_size,
                suggested_value=learned.font_size_pt.value,
                confidence=learned.font_size_pt.confidence,
                reason=f"Learned from {learned.font_size_pt.sample_count} documents: "
                       f"{learned.font_size_pt.agreement:.0%} use {learned.font_size_pt.value}pt",
            ))

    # Line spacing
    if learned.line_spacing and learned.line_spacing.confidence >= _OVERRIDE_CONFIDENCE:
        existing_spacing = existing_pf.get("line_spacing")
        if existing_spacing and existing_spacing != learned.line_spacing.value:
            recommendations.append(FormatRecommendation(
                field="page_format.line_spacing",
                current_value=existing_spacing,
                suggested_value=learned.line_spacing.value,
                confidence=learned.line_spacing.confidence,
                reason=f"Learned from {learned.line_spacing.sample_count} documents",
            ))

    # Margins
    margin_fields = [
        ("margin_top_inches", "margin_top"),
        ("margin_bottom_inches", "margin_bottom"),
        ("margin_left_inches", "margin_left"),
        ("margin_right_inches", "margin_right"),
    ]
    for yaml_key, learned_attr in margin_fields:
        learned_val: LearnedValue | None = getattr(learned, learned_attr, None)
        if learned_val and learned_val.confidence >= _OVERRIDE_CONFIDENCE:
            existing_val = existing_pf.get(yaml_key)
            if existing_val and existing_val != learned_val.value:
                recommendations.append(FormatRecommendation(
                    field=f"page_format.{yaml_key}",
                    current_value=existing_val,
                    suggested_value=learned_val.value,
                    confidence=learned_val.confidence,
                    reason=f"Learned from {learned_val.sample_count} documents: "
                           f"{learned_val.agreement:.0%} agreement",
                ))

    # Heading styles
    existing_headings = {
        h["level"]: h for h in existing.get("heading_rules", [])
    }
    for style in learned.heading_styles:
        eh = existing_headings.get(style.level, {})

        if style.case_style and style.case_style.confidence >= _OVERRIDE_CONFIDENCE:
            if eh.get("case_style") and eh["case_style"] != style.case_style.value:
                recommendations.append(FormatRecommendation(
                    field=f"heading_rules[level={style.level}].case_style",
                    current_value=eh["case_style"],
                    suggested_value=style.case_style.value,
                    confidence=style.case_style.confidence,
                    reason=f"Level {style.level} headings: {style.case_style.agreement:.0%} "
                           f"of documents use {style.case_style.value}",
                ))

        if style.alignment and style.alignment.confidence >= _OVERRIDE_CONFIDENCE:
            if eh.get("alignment") and eh["alignment"] != style.alignment.value:
                recommendations.append(FormatRecommendation(
                    field=f"heading_rules[level={style.level}].alignment",
                    current_value=eh["alignment"],
                    suggested_value=style.alignment.value,
                    confidence=style.alignment.confidence,
                    reason=f"Level {style.level} headings: {style.alignment.agreement:.0%} "
                           f"of documents use {style.alignment.value} alignment",
                ))

    return recommendations


class FormatRecommendation:
    """A specific recommendation from the ML to change a formatting rule."""

    def __init__(
        self,
        field: str,
        current_value: object,
        suggested_value: object,
        confidence: float,
        reason: str,
    ):
        self.field = field
        self.current_value = current_value
        self.suggested_value = suggested_value
        self.confidence = confidence
        self.reason = reason

    def to_dict(self) -> dict:
        return {
            "field": self.field,
            "current_value": self.current_value,
            "suggested_value": self.suggested_value,
            "confidence": self.confidence,
            "reason": self.reason,
        }

    def __repr__(self) -> str:
        return (
            f"Recommendation({self.field}: {self.current_value} -> "
            f"{self.suggested_value} [{self.confidence:.0%}])"
        )


def _section_id_to_name(section_id: str) -> str:
    """Convert a section ID to a human-readable canonical name."""
    names = {
        "table_of_contents": "Table of Contents",
        "table_of_authorities": "Table of Authorities",
        "statement_of_issues": "Issues Presented",
        "statement_of_case": "Statement of the Case",
        "statement_of_facts": "Statement of Facts",
        "statement_of_case_and_facts": "Statement of the Case and Facts",
        "summary_of_argument": "Summary of Argument",
        "argument": "Argument",
        "conclusion": "Conclusion",
        "certificate_of_compliance": "Certificate of Compliance",
        "certificate_of_service": "Certificate of Service",
        "appendix": "Appendix",
        "introduction": "Introduction",
        "standard_of_review": "Standard of Review",
        "jurisdictional_statement": "Jurisdictional Statement",
        "position_on_oral_argument": "Position on Oral Argument and Publication",
        "certifications": "Certifications",
    }
    return names.get(section_id, section_id.replace("_", " ").title())
