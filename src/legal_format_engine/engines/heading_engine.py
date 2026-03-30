"""Heading normalization engine.

Applies case, numbering, and alignment rules to section headings.
"""

from __future__ import annotations

from legal_format_engine.models.document import Alignment, HeadingLevel, Section
from legal_format_engine.rules.schema import HeadingRule, Ruleset
from legal_format_engine.utils.numbering import generate_prefix, strip_numbering_prefix
from legal_format_engine.utils.text import to_sentence_case, to_title_case, to_upper


def normalize_headings(sections: list[Section], ruleset: Ruleset) -> list[Section]:
    """Normalize all headings in a section list according to rules.

    Applies case transformation, regenerates numbering prefixes,
    and sets alignment based on the ruleset's heading rules.

    Args:
        sections: List of sections to normalize.
        ruleset: The active ruleset with heading rules.

    Returns:
        The same sections with headings normalized (mutated in place and returned).
    """
    _normalize_level(sections, HeadingLevel.LEVEL_1, ruleset)

    for section in sections:
        if section.subsections:
            _normalize_level(section.subsections, HeadingLevel.LEVEL_2, ruleset)
            for sub in section.subsections:
                if sub.subsections:
                    _normalize_level(sub.subsections, HeadingLevel.LEVEL_3, ruleset)
                    for subsub in sub.subsections:
                        if subsub.subsections:
                            _normalize_level(
                                subsub.subsections, HeadingLevel.LEVEL_4, ruleset
                            )

    return sections


def _normalize_level(
    sections: list[Section],
    level: HeadingLevel,
    ruleset: Ruleset,
) -> None:
    """Normalize headings at a specific level among siblings."""
    rule = ruleset.get_heading_rule(level)
    if not rule:
        return

    for i, section in enumerate(sections):
        # Strip any existing numbering prefix
        _, bare_text = strip_numbering_prefix(section.heading_text)

        # Apply case transformation
        normalized = _apply_case(bare_text, rule.case_style)

        # Generate new numbering prefix
        prefix = generate_prefix(i + 1, rule.numbering)

        section.heading_text = normalized
        section.heading_level = level
        section.numbering_prefix = prefix


def _apply_case(text: str, case_style: str) -> str:
    """Apply a case transformation to heading text.

    Args:
        text: The heading text (without numbering prefix).
        case_style: One of "upper", "title", "sentence".

    Returns:
        Transformed text.
    """
    match case_style:
        case "upper":
            return to_upper(text)
        case "title":
            return to_title_case(text)
        case "sentence":
            return to_sentence_case(text)
        case _:
            return text


def normalize_single_heading(text: str, rule: HeadingRule, index: int = 0) -> tuple[str, str | None]:
    """Normalize a single heading string.

    Args:
        text: Raw heading text.
        rule: The heading rule to apply.
        index: 0-based position among siblings (for numbering).

    Returns:
        Tuple of (normalized_text, numbering_prefix).
    """
    _, bare = strip_numbering_prefix(text)
    normalized = _apply_case(bare, rule.case_style)
    prefix = generate_prefix(index + 1, rule.numbering)
    return normalized, prefix
