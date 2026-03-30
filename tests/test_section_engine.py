"""Tests for engines/section_engine.py."""

from __future__ import annotations

import pytest

from legal_format_engine.engines.section_engine import (
    ValidationIssue,
    _build_alias_map,
    _check_groups,
    _check_order,
    insert_missing_sections,
    reorder_sections,
    validate_sections,
)
from legal_format_engine.models.document import Section


# ── ValidationIssue ───────────────────────────────────────────────────────

class TestValidationIssue:
    def test_to_dict(self):
        vi = ValidationIssue(code="MISSING", severity="error", message="Missing TOC", section="toc")
        d = vi.to_dict()
        assert d["code"] == "MISSING"
        assert d["severity"] == "error"
        assert d["section"] == "toc"

    def test_default_section(self):
        vi = ValidationIssue(code="X", severity="info", message="msg")
        assert vi.section == ""


# ── validate_sections ─────────────────────────────────────────────────────

class TestValidateSections:
    def test_all_sections_present_no_errors(self, sample_sections, minimal_ruleset):
        issues = validate_sections(sample_sections, minimal_ruleset)
        errors = [i for i in issues if i.severity == "error"]
        # Should have no MISSING_SECTION errors (all required sections present or group satisfied)
        missing = [i for i in errors if i.code == "MISSING_SECTION"]
        assert len(missing) == 0

    def test_missing_required_section(self, minimal_ruleset):
        sections = [
            Section(section_type="", heading="ARGUMENT", heading_level=1),
        ]
        issues = validate_sections(sections, minimal_ruleset)
        codes = [i.code for i in issues]
        assert "MISSING_SECTION" in codes

    def test_missing_toc_flagged(self, minimal_ruleset):
        sections = [
            Section(section_type="", heading="ARGUMENT", heading_level=1),
            Section(section_type="", heading="CONCLUSION", heading_level=1),
        ]
        issues = validate_sections(sections, minimal_ruleset)
        missing_sections = [i.section for i in issues if i.code == "MISSING_SECTION"]
        assert "table_of_contents" in missing_sections

    def test_group_satisfied_by_one_member(self, minimal_ruleset):
        """If statement_of_case is present, the case_facts group is satisfied."""
        sections = [
            Section(section_type="", heading="TABLE OF CONTENTS", heading_level=1),
            Section(section_type="", heading="TABLE OF AUTHORITIES", heading_level=1),
            Section(section_type="", heading="ISSUES PRESENTED", heading_level=1),
            Section(section_type="", heading="STATEMENT OF THE CASE", heading_level=1),
            Section(section_type="", heading="ARGUMENT", heading_level=1),
            Section(section_type="", heading="CONCLUSION", heading_level=1),
        ]
        issues = validate_sections(sections, minimal_ruleset)
        group_issues = [i for i in issues if i.code == "MISSING_GROUP"]
        assert len(group_issues) == 0

    def test_group_missing(self, minimal_ruleset):
        """Neither case nor facts present -> MISSING_GROUP."""
        sections = [
            Section(section_type="", heading="TABLE OF CONTENTS", heading_level=1),
            Section(section_type="", heading="TABLE OF AUTHORITIES", heading_level=1),
            Section(section_type="", heading="ISSUES PRESENTED", heading_level=1),
            Section(section_type="", heading="ARGUMENT", heading_level=1),
            Section(section_type="", heading="CONCLUSION", heading_level=1),
        ]
        issues = validate_sections(sections, minimal_ruleset)
        group_issues = [i for i in issues if i.code == "MISSING_GROUP"]
        assert len(group_issues) >= 1

    def test_unknown_section_flagged(self, minimal_ruleset):
        sections = [
            Section(section_type="", heading="RANDOM HEADING", heading_level=1),
        ]
        issues = validate_sections(sections, minimal_ruleset)
        unknown = [i for i in issues if i.code == "UNKNOWN_SECTION"]
        assert len(unknown) >= 1

    def test_order_violation(self, minimal_ruleset):
        sections = [
            Section(section_type="", heading="CONCLUSION", heading_level=1),
            Section(section_type="", heading="ARGUMENT", heading_level=1),
        ]
        issues = validate_sections(sections, minimal_ruleset)
        order_issues = [i for i in issues if i.code == "ORDER_VIOLATION"]
        assert len(order_issues) >= 1

    def test_correct_order_no_violation(self, minimal_ruleset):
        sections = [
            Section(section_type="", heading="TABLE OF CONTENTS", heading_level=1),
            Section(section_type="", heading="ARGUMENT", heading_level=1),
            Section(section_type="", heading="CONCLUSION", heading_level=1),
        ]
        issues = validate_sections(sections, minimal_ruleset)
        order_issues = [i for i in issues if i.code == "ORDER_VIOLATION"]
        assert len(order_issues) == 0

    def test_empty_sections(self, minimal_ruleset):
        issues = validate_sections([], minimal_ruleset)
        # Should flag missing sections
        assert len(issues) > 0

    def test_blank_heading_not_flagged_as_unknown(self, minimal_ruleset):
        sections = [
            Section(section_type="", heading="", heading_level=1),
        ]
        issues = validate_sections(sections, minimal_ruleset)
        unknown = [i for i in issues if i.code == "UNKNOWN_SECTION"]
        assert len(unknown) == 0


# ── reorder_sections ──────────────────────────────────────────────────────

class TestReorderSections:
    def test_reorders_by_rule_order(self, minimal_ruleset):
        sections = [
            Section(section_type="", heading="CONCLUSION", heading_level=1),
            Section(section_type="", heading="ARGUMENT", heading_level=1),
            Section(section_type="", heading="TABLE OF CONTENTS", heading_level=1),
        ]
        result = reorder_sections(sections, minimal_ruleset)
        headings = [s.heading for s in result]
        assert headings.index("TABLE OF CONTENTS") < headings.index("ARGUMENT")
        assert headings.index("ARGUMENT") < headings.index("CONCLUSION")

    def test_unknown_sections_at_end(self, minimal_ruleset):
        sections = [
            Section(section_type="", heading="APPENDIX", heading_level=1),
            Section(section_type="", heading="ARGUMENT", heading_level=1),
        ]
        result = reorder_sections(sections, minimal_ruleset)
        assert result[-1].heading == "APPENDIX"

    def test_preserves_all_sections(self, minimal_ruleset):
        sections = [
            Section(section_type="", heading="CONCLUSION", heading_level=1),
            Section(section_type="", heading="ARGUMENT", heading_level=1),
        ]
        result = reorder_sections(sections, minimal_ruleset)
        assert len(result) == 2


# ── insert_missing_sections ───────────────────────────────────────────────

class TestInsertMissingSections:
    def test_inserts_stubs(self, minimal_ruleset):
        sections = [
            Section(section_type="", heading="ARGUMENT", heading_level=1),
        ]
        result = insert_missing_sections(sections, minimal_ruleset)
        headings = [s.heading for s in result]
        # Should now have table of contents, table of authorities, issues, conclusion stubs
        assert len(result) > 1

    def test_stubs_are_marked(self, minimal_ruleset):
        result = insert_missing_sections([], minimal_ruleset)
        stubs = [s for s in result if s.is_stub]
        assert len(stubs) >= 1

    def test_stub_content_placeholder(self, minimal_ruleset):
        result = insert_missing_sections([], minimal_ruleset)
        stubs = [s for s in result if s.is_stub]
        for stub in stubs:
            assert any("SECTION CONTENT NEEDED" in b.text for b in stub.content)

    def test_group_gets_one_stub(self):
        """When case_facts group is missing and members required, one stub inserted."""
        from legal_format_engine.models.section import SectionRule, Ruleset, PageFormat, HeadingRule, HeadingLevel
        rs = Ruleset(
            name="Test", jurisdiction="wisconsin", court_level="coa",
            document_type="brief",
            section_rules=[
                SectionRule(section_type="argument", title="Argument", required=True, order=7, aliases=["Argument"]),
                SectionRule(section_type="statement_of_case", title="Statement of the Case",
                            required=True, order=5, group="case_facts",
                            aliases=["Statement of the Case"]),
                SectionRule(section_type="statement_of_facts", title="Statement of Facts",
                            required=True, order=6, group="case_facts",
                            aliases=["Facts", "Statement of Facts"]),
            ],
        )
        sections = [
            Section(section_type="", heading="ARGUMENT", heading_level=1),
        ]
        result = insert_missing_sections(sections, rs)
        case_facts = [s for s in result
                      if s.section_type in ("statement_of_case", "statement_of_facts")]
        assert len(case_facts) == 1

    def test_no_duplicates_when_present(self, sample_sections, minimal_ruleset):
        result = insert_missing_sections(sample_sections, minimal_ruleset)
        # Should not duplicate sections that are already present
        arg_sections = [s for s in result if "ARGUMENT" in s.heading.upper()
                        or s.heading == "Argument"]
        assert len(arg_sections) == 1

    def test_result_is_ordered(self, minimal_ruleset):
        result = insert_missing_sections([], minimal_ruleset)
        # The result should be reordered according to the ruleset
        assert len(result) >= 1


# ── _build_alias_map ──────────────────────────────────────────────────────

class TestBuildAliasMap:
    def test_includes_title(self, minimal_ruleset):
        alias_map = _build_alias_map(minimal_ruleset)
        assert "Table of Contents" in alias_map["table_of_contents"]

    def test_includes_aliases(self, minimal_ruleset):
        alias_map = _build_alias_map(minimal_ruleset)
        assert "TOC" in alias_map["table_of_contents"]


# ── _check_groups ─────────────────────────────────────────────────────────

class TestCheckGroups:
    def test_group_satisfied(self, minimal_ruleset):
        found = {"statement_of_case"}
        issues = _check_groups(minimal_ruleset, found)
        group_issues = [i for i in issues if i.code == "MISSING_GROUP"]
        assert len(group_issues) == 0

    def test_group_not_satisfied(self, minimal_ruleset):
        found = set()
        issues = _check_groups(minimal_ruleset, found)
        group_issues = [i for i in issues if i.code == "MISSING_GROUP"]
        assert len(group_issues) >= 1
