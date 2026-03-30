"""Section engine - validates, reorders, and inserts required sections."""

from __future__ import annotations
from typing import Optional

from legal_format_engine.models.document import ContentBlock, Section
from legal_format_engine.models.section import Ruleset, SectionRule
from legal_format_engine.utils.text import fuzzy_heading_match, normalize_heading


class ValidationIssue:
    """Represents a document validation issue."""

    def __init__(self, code: str, severity: str, message: str, section: str = ""):
        self.code = code
        self.severity = severity  # "error", "warning", "info"
        self.message = message
        self.section = section

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "section": self.section,
        }


def validate_sections(
    sections: list[Section],
    ruleset: Ruleset,
) -> list[ValidationIssue]:
    """Validate document sections against ruleset rules.

    Checks for:
    - Missing required sections
    - Section order violations
    - Unknown sections
    - Group constraints (e.g., combined vs separate case/facts)
    """
    issues: list[ValidationIssue] = []

    # Build alias map for fuzzy matching
    alias_map = _build_alias_map(ruleset)

    # Identify each section's type
    identified: list[tuple[Section, str | None]] = []
    for section in sections:
        section_type = fuzzy_heading_match(section.heading, alias_map)
        identified.append((section, section_type))

    found_types = {st for _, st in identified if st is not None}

    # Check required sections
    for rule in ruleset.section_rules:
        if rule.required and rule.section_type not in found_types:
            # Check if part of a group
            if rule.group:
                continue  # Handle groups separately below
            issues.append(ValidationIssue(
                code="MISSING_SECTION",
                severity="error",
                message=f"Missing required section: {rule.title or rule.section_type}",
                section=rule.section_type,
            ))

    # Check group constraints
    issues.extend(_check_groups(ruleset, found_types))

    # Check section order
    order_issues = _check_order(identified, ruleset)
    issues.extend(order_issues)

    # Flag unknown sections
    for section, section_type in identified:
        if section_type is None and section.heading.strip():
            issues.append(ValidationIssue(
                code="UNKNOWN_SECTION",
                severity="info",
                message=f"Unknown section: '{section.heading}'",
                section="",
            ))

    return issues


def _check_groups(ruleset: Ruleset, found_types: set[str]) -> list[ValidationIssue]:
    """Check group constraints - at least one member of each required group must be present."""
    issues = []
    groups: dict[str, list[SectionRule]] = {}
    for rule in ruleset.section_rules:
        if rule.group:
            groups.setdefault(rule.group, []).append(rule)

    for group_name, group_rules in groups.items():
        # Check if any required group has at least one member present
        has_required = any(r.required or True for r in group_rules)  # Groups imply at least one needed
        has_member = any(r.section_type in found_types for r in group_rules)
        if not has_member and has_required:
            member_names = [r.title or r.section_type for r in group_rules]
            issues.append(ValidationIssue(
                code="MISSING_GROUP",
                severity="error",
                message=f"At least one of these sections is required: {', '.join(member_names)}",
                section=group_name,
            ))
    return issues


def _build_alias_map(ruleset: Ruleset) -> dict[str, list[str]]:
    """Build a mapping of section_type -> list of aliases for fuzzy matching."""
    alias_map: dict[str, list[str]] = {}
    for rule in ruleset.section_rules:
        aliases = list(rule.aliases)
        if rule.title:
            aliases.append(rule.title)
        alias_map[rule.section_type] = aliases
    return alias_map


def _check_order(
    identified: list[tuple[Section, str | None]],
    ruleset: Ruleset,
) -> list[ValidationIssue]:
    """Check that identified sections are in the correct order."""
    issues = []
    order_map = {r.section_type: r.order for r in ruleset.section_rules}

    prev_order = -1
    prev_name = ""
    for section, section_type in identified:
        if section_type is None:
            continue
        order = order_map.get(section_type, 999)
        if order < prev_order:
            issues.append(ValidationIssue(
                code="ORDER_VIOLATION",
                severity="warning",
                message=f"'{section.heading}' appears after '{prev_name}' but should come before it",
                section=section_type,
            ))
        prev_order = order
        prev_name = section.heading

    return issues


def reorder_sections(
    sections: list[Section],
    ruleset: Ruleset,
) -> list[Section]:
    """Reorder sections to match the ruleset's expected order."""
    alias_map = _build_alias_map(ruleset)
    order_map = {r.section_type: r.order for r in ruleset.section_rules}

    identified: list[tuple[Section, str | None]] = []
    for section in sections:
        section_type = fuzzy_heading_match(section.heading, alias_map)
        identified.append((section, section_type))

    def sort_key(item: tuple[Section, str | None]) -> int:
        _, st = item
        if st is None:
            return 999
        return order_map.get(st, 999)

    identified.sort(key=sort_key)
    return [section for section, _ in identified]


def insert_missing_sections(
    sections: list[Section],
    ruleset: Ruleset,
) -> list[Section]:
    """Insert stub sections for any required sections that are missing."""
    alias_map = _build_alias_map(ruleset)
    found_types = set()
    for section in sections:
        st = fuzzy_heading_match(section.heading, alias_map)
        if st:
            found_types.add(st)

    # Check groups
    groups: dict[str, list[SectionRule]] = {}
    for rule in ruleset.section_rules:
        if rule.group:
            groups.setdefault(rule.group, []).append(rule)

    satisfied_groups = set()
    for group_name, group_rules in groups.items():
        if any(r.section_type in found_types for r in group_rules):
            satisfied_groups.add(group_name)

    new_sections = list(sections)

    # First pass: insert stubs for required non-group sections
    for rule in ruleset.section_rules:
        if not rule.required:
            continue
        if rule.group:
            continue  # Handle groups separately
        if rule.section_type in found_types:
            continue
        stub = Section(
            section_type=rule.section_type,
            heading=rule.title or rule.section_type.replace("_", " ").title(),
            heading_level=rule.heading_level,
            content=[ContentBlock(text="[SECTION CONTENT NEEDED]", is_body_text=True)],
            is_stub=True,
        )
        new_sections.append(stub)

    # Second pass: insert stubs for unsatisfied groups
    for group_name, group_rules in groups.items():
        if group_name in satisfied_groups:
            continue
        # Insert the first member of the group as a stub
        first_rule = group_rules[0]
        stub = Section(
            section_type=first_rule.section_type,
            heading=first_rule.title or first_rule.section_type.replace("_", " ").title(),
            heading_level=first_rule.heading_level,
            content=[ContentBlock(text="[SECTION CONTENT NEEDED]", is_body_text=True)],
            is_stub=True,
        )
        new_sections.append(stub)
        satisfied_groups.add(group_name)

    return reorder_sections(new_sections, ruleset)
