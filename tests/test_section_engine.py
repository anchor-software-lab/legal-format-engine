"""Tests for section validation and reordering engine."""

from legal_format_engine.engines.section_engine import (
    insert_missing_sections,
    reorder_sections,
    validate_sections,
)
from legal_format_engine.models.document import (
    ContentBlock,
    HeadingLevel,
    LegalDocument,
    Section,
    Severity,
)
from legal_format_engine.parsers.plain_text_parser import parse_plain_text


class TestValidateSections:
    def test_all_present(self, sample_brief_text, wi_appellate_ruleset):
        doc = parse_plain_text(sample_brief_text)
        doc = validate_sections(doc, wi_appellate_ruleset)
        missing = [i for i in doc.issues if i.code == "MISSING_SECTION"]
        # Sample brief has most sections but may be missing some
        # At minimum, statement_of_issues, statement_of_case, statement_of_facts,
        # argument, and conclusion should be found
        found_ids = set()
        aliases = wi_appellate_ruleset.get_section_aliases()
        from legal_format_engine.utils.text import fuzzy_heading_match
        for s in doc.sections:
            m = fuzzy_heading_match(s.heading_text, aliases)
            if m:
                found_ids.add(m)
        assert "argument" in found_ids
        assert "conclusion" in found_ids

    def test_flags_missing(self, wi_appellate_ruleset):
        doc = LegalDocument(sections=[
            Section(
                id="argument",
                heading_text="ARGUMENT",
                heading_level=HeadingLevel.LEVEL_1,
                content=[ContentBlock(text="Some text.")],
            )
        ])
        doc = validate_sections(doc, wi_appellate_ruleset)
        missing = [i for i in doc.issues if i.code == "MISSING_SECTION"]
        assert len(missing) > 0
        missing_ids = [i.section_id for i in missing]
        assert "conclusion" in missing_ids


class TestReorderSections:
    def test_reorders_correctly(self, wi_appellate_ruleset):
        # Create sections in wrong order
        doc = LegalDocument(sections=[
            Section(id="arg", heading_text="ARGUMENT",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
            Section(id="facts", heading_text="STATEMENT OF FACTS",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
            Section(id="issues", heading_text="STATEMENT OF ISSUES",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
        ])
        doc = reorder_sections(doc, wi_appellate_ruleset)
        headings = [s.heading_text for s in doc.sections]
        assert headings.index("STATEMENT OF ISSUES") < headings.index("STATEMENT OF FACTS")
        assert headings.index("STATEMENT OF FACTS") < headings.index("ARGUMENT")

    def test_preserves_unmatched(self, wi_appellate_ruleset):
        doc = LegalDocument(sections=[
            Section(id="custom", heading_text="PRELIMINARY STATEMENT",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
            Section(id="arg", heading_text="ARGUMENT",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
        ])
        doc = reorder_sections(doc, wi_appellate_ruleset)
        assert len(doc.sections) == 2
        # Unmatched section should be at the end
        assert doc.sections[-1].heading_text == "PRELIMINARY STATEMENT"


class TestInsertMissing:
    def test_inserts_stubs(self, wi_appellate_ruleset):
        doc = LegalDocument(sections=[
            Section(id="arg", heading_text="ARGUMENT",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
        ])
        doc = insert_missing_sections(doc, wi_appellate_ruleset)
        assert len(doc.sections) > 1
        generated = [s for s in doc.sections if s.is_generated]
        assert len(generated) > 0


class TestGroupValidation:
    def test_combined_case_facts_satisfies_group(self):
        from legal_format_engine.rules.loader import load_ruleset
        rs = load_ruleset("wisconsin", "appellate", "brief", variant="spd")
        doc = LegalDocument(sections=[
            Section(id="toc", heading_text="TABLE OF CONTENTS",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
            Section(id="toa", heading_text="TABLE OF AUTHORITIES",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
            Section(id="issues", heading_text="ISSUES PRESENTED",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
            Section(id="oral", heading_text="POSITION ON ORAL ARGUMENT AND PUBLICATION",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
            Section(id="casefacts", heading_text="STATEMENT OF THE CASE AND FACTS",
                    heading_level=HeadingLevel.LEVEL_1, content=[ContentBlock(text="Facts here.")]),
            Section(id="arg", heading_text="ARGUMENT",
                    heading_level=HeadingLevel.LEVEL_1, content=[ContentBlock(text="Arg.")]),
            Section(id="conc", heading_text="CONCLUSION",
                    heading_level=HeadingLevel.LEVEL_1, content=[ContentBlock(text="Done.")]),
            Section(id="cert", heading_text="CERTIFICATIONS",
                    heading_level=HeadingLevel.LEVEL_1, content=[ContentBlock(text="I certify.")]),
        ])
        doc = validate_sections(doc, rs)
        group_issues = [i for i in doc.issues if i.code == "MISSING_SECTION_GROUP"]
        assert len(group_issues) == 0

    def test_separate_case_facts_satisfies_group(self):
        from legal_format_engine.rules.loader import load_ruleset
        rs = load_ruleset("wisconsin", "appellate", "brief", variant="spd")
        doc = LegalDocument(sections=[
            Section(id="case", heading_text="STATEMENT OF THE CASE",
                    heading_level=HeadingLevel.LEVEL_1, content=[ContentBlock(text="Case.")]),
            Section(id="facts", heading_text="STATEMENT OF FACTS",
                    heading_level=HeadingLevel.LEVEL_1, content=[ContentBlock(text="Facts.")]),
            Section(id="arg", heading_text="ARGUMENT",
                    heading_level=HeadingLevel.LEVEL_1, content=[ContentBlock(text="Arg.")]),
        ])
        doc = validate_sections(doc, rs)
        group_issues = [i for i in doc.issues if i.code == "MISSING_SECTION_GROUP"]
        assert len(group_issues) == 0

    def test_missing_all_case_facts_flags_group(self):
        from legal_format_engine.rules.loader import load_ruleset
        rs = load_ruleset("wisconsin", "appellate", "brief", variant="spd")
        doc = LegalDocument(sections=[
            Section(id="arg", heading_text="ARGUMENT",
                    heading_level=HeadingLevel.LEVEL_1, content=[ContentBlock(text="Arg.")]),
        ])
        doc = validate_sections(doc, rs)
        group_issues = [i for i in doc.issues if i.code == "MISSING_SECTION_GROUP"]
        assert len(group_issues) == 1
        assert "Statement of the Case" in group_issues[0].message
