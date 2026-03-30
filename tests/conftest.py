"""Shared fixtures for the legal-format-engine test suite."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from legal_format_engine.models.document import (
    Attorney,
    CaseMetadata,
    ContentBlock,
    DocumentMetadata,
    DocumentModel,
    Party,
    PartyRole,
    Section,
)
from legal_format_engine.models.caption import CaptionBlock
from legal_format_engine.models.section import (
    CertificationTemplate,
    HeadingLevel,
    HeadingRule,
    PageFormat,
    Ruleset,
    SectionRule,
)
from legal_format_engine.models.patterns import (
    BriefAnalysis,
    FontPattern,
    FormatProfile,
    HeadingPattern,
    MarginPattern,
    SectionPattern,
)
from legal_format_engine.rules.base import load_ruleset


# ---------------------------------------------------------------------------
# Wisconsin ruleset (loaded once)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def wi_ruleset() -> Ruleset:
    """Load the real Wisconsin appellate brief ruleset."""
    return load_ruleset("wisconsin", "appellate_brief")


# ---------------------------------------------------------------------------
# Minimal ruleset for unit tests (no I/O)
# ---------------------------------------------------------------------------

@pytest.fixture()
def minimal_ruleset() -> Ruleset:
    return Ruleset(
        name="Test Ruleset",
        jurisdiction="wisconsin",
        court_level="court_of_appeals",
        document_type="appellate_brief",
        page_format=PageFormat(font_size_pt=13, margin_top_inches=1.0),
        heading_rules=[
            HeadingRule(level=1, style=HeadingLevel.TITLE_CASE_CENTERED, bold=True, centered=True),
            HeadingRule(level=2, style=HeadingLevel.ROMAN_NUMERAL, bold=True),
            HeadingRule(level=3, style=HeadingLevel.CAPITAL_LETTER, bold=True, indent_inches=0.5),
            HeadingRule(level=4, style=HeadingLevel.ARABIC_NUMERAL, bold=False, indent_inches=1.0),
        ],
        section_rules=[
            SectionRule(section_type="table_of_contents", title="Table of Contents", required=True, order=1, aliases=["Contents", "TOC"]),
            SectionRule(section_type="table_of_authorities", title="Table of Authorities", required=True, order=2, aliases=["Authorities Cited"]),
            SectionRule(section_type="statement_of_issues", title="Issues Presented", required=True, order=3, aliases=["Issues Presented", "Statement of the Issues"]),
            SectionRule(section_type="statement_of_case", title="Statement of the Case", required=False, order=5, group="case_facts", aliases=["Statement of the Case"]),
            SectionRule(section_type="statement_of_facts", title="Statement of Facts", required=False, order=6, group="case_facts", aliases=["Facts", "Statement of Facts"]),
            SectionRule(section_type="argument", title="Argument", required=True, order=7, aliases=["Argument"]),
            SectionRule(section_type="conclusion", title="Conclusion", required=True, order=8, aliases=["Conclusion"]),
        ],
        certification_templates=[
            CertificationTemplate(cert_type="form_length", template="Word count: {word_count}.", required=True),
            CertificationTemplate(cert_type="electronic_filing", template="E-filing cert.", required=True),
        ],
        allow_combined_case_facts=True,
    )


# ---------------------------------------------------------------------------
# Case metadata / parties / attorney
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_case_meta() -> CaseMetadata:
    return CaseMetadata(
        case_name="Smith v. Jones",
        case_number="2025AP001234",
        court_name="STATE OF WISCONSIN COURT OF APPEALS",
        district="1",
        parties=[
            Party(name="John Smith", role=PartyRole.APPELLANT, designation="Appellant"),
            Party(name="Jane Jones", role=PartyRole.RESPONDENT, designation="Respondent"),
        ],
    )


@pytest.fixture()
def sample_attorney() -> Attorney:
    return Attorney(
        name="Alice Advocate",
        bar_number="1012345",
        firm="Smith & Smith LLP",
        address="123 Main St\nMadison, WI 53703",
        phone="(608) 555-1234",
        email="alice@smithsmith.com",
        is_lead=True,
    )


# ---------------------------------------------------------------------------
# Document metadata
# ---------------------------------------------------------------------------

@pytest.fixture()
def default_doc_meta() -> DocumentMetadata:
    return DocumentMetadata()


# ---------------------------------------------------------------------------
# Sample sections list
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_sections() -> list[Section]:
    return [
        Section(section_type="", heading="TABLE OF CONTENTS", heading_level=1),
        Section(section_type="", heading="TABLE OF AUTHORITIES", heading_level=1),
        Section(section_type="", heading="ISSUES PRESENTED", heading_level=1, content=[
            ContentBlock(text="Whether the circuit court erred.", is_body_text=True),
        ]),
        Section(section_type="", heading="STATEMENT OF THE CASE", heading_level=1, content=[
            ContentBlock(text="This case arises from...", is_body_text=True),
        ]),
        Section(section_type="", heading="ARGUMENT", heading_level=1, content=[
            ContentBlock(text="The court should reverse because...", is_body_text=True),
        ]),
        Section(section_type="", heading="CONCLUSION", heading_level=1, content=[
            ContentBlock(text="For the foregoing reasons...", is_body_text=True),
        ]),
    ]


# ---------------------------------------------------------------------------
# Sample plain text for parsing
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_brief_text() -> str:
    return """\
TABLE OF CONTENTS

TABLE OF AUTHORITIES

ISSUES PRESENTED

Whether the circuit court erred in granting summary judgment.

STATEMENT OF THE CASE

This case arises from a dispute between the parties.
The circuit court granted summary judgment on January 1, 2025.

ARGUMENT

I. The Standard of Review Is De Novo

This Court reviews summary judgment de novo.

II. The Circuit Court Erred

The circuit court erred by misapplying the law.

A. First sub-argument

The first point is important.

CONCLUSION

For the foregoing reasons, this Court should reverse.
"""


# ---------------------------------------------------------------------------
# Temp directory for I/O tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_dir(tmp_path):
    return tmp_path
