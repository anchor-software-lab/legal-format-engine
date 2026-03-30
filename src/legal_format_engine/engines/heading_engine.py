"""Heading engine - normalizes heading styles, capitalization, and numbering."""

from __future__ import annotations

from legal_format_engine.models.document import Section
from legal_format_engine.models.section import HeadingLevel, HeadingRule, Ruleset
from legal_format_engine.utils.text import (
    is_all_caps,
    to_all_caps,
    to_sentence_case,
    to_title_case,
)
from legal_format_engine.utils.numbering import (
    generate_prefix,
    strip_numbering_prefix,
)


def normalize_headings(
    sections: list[Section],
    ruleset: Ruleset,
) -> list[Section]:
    """Normalize all heading styles according to ruleset rules.

    Applies correct capitalization and numbering to each section heading.
    """
    heading_rules_map: dict[int, HeadingRule] = {
        hr.level: hr for hr in ruleset.heading_rules
    }

    counters: dict[int, int] = {}
    return [
        _normalize_section(s, heading_rules_map, counters)
        for s in sections
    ]


def _normalize_section(
    section: Section,
    heading_rules_map: dict[int, HeadingRule],
    counters: dict[int, int],
) -> Section:
    """Normalize a single section heading and recurse into subsections."""
    level = section.heading_level
    rule = heading_rules_map.get(level)

    if rule:
        # Strip existing prefix
        clean = strip_numbering_prefix(section.heading)

        # Apply capitalization
        section.heading = _apply_case(clean, rule.style)

        # Apply numbering
        numbering_type = _style_to_numbering(rule.style)
        if numbering_type:
            counters[level] = counters.get(level, 0) + 1
            prefix = generate_prefix(counters[level], numbering_type)
            section.numbering_prefix = prefix
        else:
            section.numbering_prefix = None

    # Recurse into subsections, reset lower-level counters
    sub_counters: dict[int, int] = {}
    section.subsections = [
        _normalize_section(sub, heading_rules_map, sub_counters)
        for sub in section.subsections
    ]

    return section


def _apply_case(text: str, style: HeadingLevel) -> str:
    """Apply the correct case transformation for a heading style."""
    if style in (HeadingLevel.ALL_CAPS_CENTERED, HeadingLevel.ALL_CAPS_LEFT):
        return to_all_caps(text)
    elif style in (HeadingLevel.TITLE_CASE_CENTERED, HeadingLevel.TITLE_CASE_LEFT):
        return to_title_case(text)
    elif style == HeadingLevel.SENTENCE_CASE:
        return to_sentence_case(text)
    else:
        # roman_numeral, capital_letter, arabic_numeral keep title case
        return to_title_case(text)


def _style_to_numbering(style: HeadingLevel) -> str | None:
    """Map heading style to numbering type."""
    mapping = {
        HeadingLevel.ROMAN_NUMERAL: "roman",
        HeadingLevel.CAPITAL_LETTER: "alpha",
        HeadingLevel.ARABIC_NUMERAL: "arabic",
    }
    return mapping.get(style)
