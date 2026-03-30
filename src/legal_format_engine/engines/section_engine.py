"""Section validation and reordering engine.

Validates that required sections exist, are in correct order,
and handles missing/unknown sections.
"""

from __future__ import annotations

from legal_format_engine.models.document import (
    ContentBlock,
    HeadingLevel,
    LegalDocument,
    Section,
    Severity,
    ValidationIssue,
)
from legal_format_engine.rules.schema import RequiredSection, Ruleset
from legal_format_engine.utils.text import fuzzy_heading_match, normalize_for_matching


def validate_sections(doc: LegalDocument, ruleset: Ruleset) -> LegalDocument:
    """Validate that required sections exist in the document.

    Adds ValidationIssue entries for missing required sections
    and unknown sections.

    Args:
        doc: The document to validate.
        ruleset: The active ruleset.

    Returns:
        The document with issues populated.
    """
    aliases = ruleset.get_section_aliases()
    matched_ids: set[str] = set()

    for section in doc.sections:
        match = fuzzy_heading_match(section.heading_text, aliases)
        if match:
            matched_ids.add(match)
        elif section.heading_text and section.id != "preamble":
            doc.issues.append(ValidationIssue(
                severity=Severity.INFO,
                code="UNKNOWN_SECTION",
                message=f"Section '{section.heading_text}' does not match any known section type.",
                section_id=section.id,
            ))

    # Check for missing required sections
    for req in ruleset.required_sections:
        if req.required and req.id not in matched_ids:
            doc.issues.append(ValidationIssue(
                severity=Severity.WARNING,
                code="MISSING_SECTION",
                message=f"Required section '{req.canonical_name}' is missing.",
                section_id=req.id,
                auto_fixable=True,
            ))

    # Check group constraints: at least one section in each group must exist
    _check_groups(doc, ruleset, matched_ids)

    # Check section order
    _check_order(doc, ruleset, aliases)

    return doc


def reorder_sections(doc: LegalDocument, ruleset: Ruleset) -> LegalDocument:
    """Reorder sections to match the canonical order defined in the ruleset.

    Matched sections are placed in rule order. Unmatched sections
    are appended at the end (never discarded).

    Args:
        doc: The document to reorder.
        ruleset: The active ruleset.

    Returns:
        The document with sections reordered.
    """
    aliases = ruleset.get_section_aliases()
    rule_order = {req.id: req.order for req in ruleset.required_sections}

    # Map each section to its rule id (if matched)
    matched: dict[str, Section] = {}
    unmatched: list[Section] = []

    for section in doc.sections:
        match = fuzzy_heading_match(section.heading_text, aliases)
        if match and match not in matched:
            matched[match] = section
        else:
            unmatched.append(section)

    # Build reordered list: matched sections in rule order, then unmatched
    ordered: list[Section] = []
    for req in sorted(ruleset.required_sections, key=lambda r: r.order):
        if req.id in matched:
            ordered.append(matched[req.id])

    ordered.extend(unmatched)
    doc.sections = ordered

    return doc


def insert_missing_sections(doc: LegalDocument, ruleset: Ruleset) -> LegalDocument:
    """Insert stub sections for any missing required sections.

    Stubs are inserted at the correct position with empty content
    and marked as generated.

    Args:
        doc: The document to modify.
        ruleset: The active ruleset.

    Returns:
        The document with stubs inserted.
    """
    aliases = ruleset.get_section_aliases()
    existing_ids: set[str] = set()

    for section in doc.sections:
        match = fuzzy_heading_match(section.heading_text, aliases)
        if match:
            existing_ids.add(match)

    for req in ruleset.required_sections:
        if req.required and req.id not in existing_ids:
            stub = Section(
                id=req.id,
                heading_text=req.canonical_name.upper(),
                heading_level=HeadingLevel(req.heading_level),
                content=[ContentBlock(text=f"[{req.canonical_name} - TO BE COMPLETED]")],
                is_generated=True,
            )
            # Insert at the correct position
            _insert_at_order(doc, stub, req.order, ruleset)

    return doc


def _insert_at_order(
    doc: LegalDocument,
    stub: Section,
    target_order: int,
    ruleset: Ruleset,
) -> None:
    """Insert a stub section at the correct position based on rule order."""
    aliases = ruleset.get_section_aliases()
    rule_order = {req.id: req.order for req in ruleset.required_sections}

    insert_idx = len(doc.sections)  # default: append at end

    for i, section in enumerate(doc.sections):
        match = fuzzy_heading_match(section.heading_text, aliases)
        if match and rule_order.get(match, 0) > target_order:
            insert_idx = i
            break

    doc.sections.insert(insert_idx, stub)


def _check_groups(
    doc: LegalDocument,
    ruleset: Ruleset,
    matched_ids: set[str],
) -> None:
    """Check group constraints: at least one section in each group must exist.

    Groups allow "either/or" section requirements. For example, a brief
    can have either a combined "Statement of the Case and Facts" or
    separate "Statement of the Case" and "Statement of Facts" sections.
    """
    # Collect groups
    groups: dict[str, list[RequiredSection]] = {}
    for req in ruleset.required_sections:
        if req.group:
            groups.setdefault(req.group, []).append(req)

    for group_name, members in groups.items():
        group_matched = any(m.id in matched_ids for m in members)
        if not group_matched:
            names = [m.canonical_name for m in members]
            doc.issues.append(ValidationIssue(
                severity=Severity.WARNING,
                code="MISSING_SECTION_GROUP",
                message=(
                    f"At least one of these sections is required: "
                    f"{', '.join(names)}"
                ),
                auto_fixable=False,
            ))


def _check_order(
    doc: LegalDocument,
    ruleset: Ruleset,
    aliases: dict[str, list[str]],
) -> None:
    """Check if sections are in the correct order and add warnings if not."""
    rule_order = {req.id: req.order for req in ruleset.required_sections}
    section_orders: list[tuple[str, int]] = []

    for section in doc.sections:
        match = fuzzy_heading_match(section.heading_text, aliases)
        if match and match in rule_order:
            section_orders.append((match, rule_order[match]))

    # Check if the order values are monotonically increasing
    for i in range(1, len(section_orders)):
        if section_orders[i][1] < section_orders[i - 1][1]:
            doc.issues.append(ValidationIssue(
                severity=Severity.WARNING,
                code="WRONG_ORDER",
                message=(
                    f"Section '{section_orders[i][0]}' appears before "
                    f"'{section_orders[i - 1][0]}' but should come after it."
                ),
                auto_fixable=True,
            ))
            break  # One order warning is enough to flag the problem
