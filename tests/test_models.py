"""Tests for data models: document, caption, section, patterns."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

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


# ── PartyRole ──────────────────────────────────────────────────────────────

class TestPartyRole:
    def test_all_roles_exist(self):
        expected = {"plaintiff", "defendant", "appellant", "respondent",
                    "petitioner", "intervenor", "amicus"}
        actual = {r.value for r in PartyRole}
        assert actual == expected

    def test_role_from_string(self):
        assert PartyRole("appellant") is PartyRole.APPELLANT

    def test_invalid_role_raises(self):
        with pytest.raises(ValueError):
            PartyRole("judge")


# ── Party ──────────────────────────────────────────────────────────────────

class TestParty:
    def test_create_party(self):
        p = Party(name="John Doe", role=PartyRole.PLAINTIFF)
        assert p.name == "John Doe"
        assert p.role is PartyRole.PLAINTIFF
        assert p.designation is None

    def test_party_with_designation(self):
        p = Party(name="X", role=PartyRole.APPELLANT, designation="Appellant-Cross-Respondent")
        assert p.designation == "Appellant-Cross-Respondent"

    def test_party_requires_name_and_role(self):
        with pytest.raises(ValidationError):
            Party(role=PartyRole.DEFENDANT)  # type: ignore[call-arg]


# ── Attorney ───────────────────────────────────────────────────────────────

class TestAttorney:
    def test_create_minimal(self):
        a = Attorney(name="Jane")
        assert a.name == "Jane"
        assert a.bar_number is None
        assert a.is_lead is False

    def test_create_full(self, sample_attorney):
        a = sample_attorney
        assert a.bar_number == "1012345"
        assert a.firm == "Smith & Smith LLP"
        assert a.is_lead is True

    def test_optional_fields_default_none(self):
        a = Attorney(name="X")
        for f in ("bar_number", "firm", "address", "phone", "email"):
            assert getattr(a, f) is None


# ── CaseMetadata ───────────────────────────────────────────────────────────

class TestCaseMetadata:
    def test_required_fields(self):
        cm = CaseMetadata(case_name="A v. B", case_number="123")
        assert cm.case_name == "A v. B"
        assert cm.parties == []

    def test_with_parties(self, sample_case_meta):
        assert len(sample_case_meta.parties) == 2
        assert sample_case_meta.parties[0].role is PartyRole.APPELLANT

    def test_optional_fields(self):
        cm = CaseMetadata(case_name="X", case_number="1")
        assert cm.court_name is None
        assert cm.district is None


# ── DocumentMetadata ───────────────────────────────────────────────────────

class TestDocumentMetadata:
    def test_defaults(self):
        dm = DocumentMetadata()
        assert dm.jurisdiction == "wisconsin"
        assert dm.court_level == "court_of_appeals"
        assert dm.document_type == "appellate_brief"
        assert dm.variant is None

    def test_custom_values(self):
        dm = DocumentMetadata(jurisdiction="california", court_level="supreme_court")
        assert dm.jurisdiction == "california"


# ── ContentBlock ───────────────────────────────────────────────────────────

class TestContentBlock:
    def test_defaults(self):
        cb = ContentBlock(text="Hello")
        assert cb.bold is False
        assert cb.italic is False
        assert cb.centered is False
        assert cb.is_heading is False
        assert cb.is_body_text is False
        assert cb.heading_level == 0

    def test_heading_block(self):
        cb = ContentBlock(text="TITLE", bold=True, centered=True, is_heading=True, heading_level=1)
        assert cb.is_heading
        assert cb.heading_level == 1

    def test_page_break(self):
        cb = ContentBlock(text="", is_page_break=True)
        assert cb.is_page_break


# ── Section ────────────────────────────────────────────────────────────────

class TestSection:
    def test_minimal(self):
        s = Section(section_type="argument", heading="Argument")
        assert s.heading_level == 1
        assert s.content == []
        assert s.subsections == []
        assert s.is_stub is False

    def test_with_subsections(self):
        sub = Section(section_type="sub", heading="Sub", heading_level=2)
        parent = Section(section_type="arg", heading="Arg", subsections=[sub])
        assert len(parent.subsections) == 1
        assert parent.subsections[0].heading == "Sub"

    def test_stub_section(self):
        s = Section(section_type="toc", heading="TOC", is_stub=True)
        assert s.is_stub


# ── DocumentModel ──────────────────────────────────────────────────────────

class TestDocumentModel:
    def test_minimal(self):
        doc = DocumentModel(metadata=DocumentMetadata())
        assert doc.sections == []
        assert doc.caption is None
        assert doc.signature_block is None

    def test_with_sections(self, sample_sections):
        doc = DocumentModel(metadata=DocumentMetadata(), sections=sample_sections)
        assert len(doc.sections) == 6

    def test_with_caption(self):
        caption = CaptionBlock(court_name="COURT", case_number="123", document_title="BRIEF")
        doc = DocumentModel(metadata=DocumentMetadata(), caption=caption)
        assert doc.caption.court_name == "COURT"


# ── CaptionBlock ───────────────────────────────────────────────────────────

class TestCaptionBlock:
    def test_defaults(self):
        cb = CaptionBlock()
        assert cb.court_name == ""
        assert cb.case_number == ""
        assert cb.lines == []

    def test_full(self):
        cb = CaptionBlock(
            court_name="TEST COURT",
            district="1",
            case_number="2025AP999",
            document_title="Opening Brief",
        )
        assert cb.district == "1"


# ── HeadingLevel enum ──────────────────────────────────────────────────────

class TestHeadingLevel:
    def test_all_values(self):
        assert len(HeadingLevel) == 8

    def test_title_case_centered(self):
        assert HeadingLevel.TITLE_CASE_CENTERED.value == "title_case_centered"

    def test_from_string(self):
        assert HeadingLevel("roman_numeral") is HeadingLevel.ROMAN_NUMERAL


# ── PageFormat ─────────────────────────────────────────────────────────────

class TestPageFormat:
    def test_defaults(self):
        pf = PageFormat()
        assert pf.font == "Times New Roman"
        assert pf.font_size_pt == 13.0
        assert pf.line_spacing == "double"
        assert pf.margin_top_inches == 1.0
        assert pf.first_line_indent_inches == 0.5

    def test_custom(self):
        pf = PageFormat(font_size_pt=12, margin_left_inches=1.5)
        assert pf.font_size_pt == 12
        assert pf.margin_left_inches == 1.5


# ── SectionRule ────────────────────────────────────────────────────────────

class TestSectionRule:
    def test_defaults(self):
        sr = SectionRule(section_type="arg")
        assert sr.required is True
        assert sr.order == 0
        assert sr.aliases == []
        assert sr.group is None

    def test_with_group(self):
        sr = SectionRule(section_type="case", group="case_facts")
        assert sr.group == "case_facts"


# ── CertificationTemplate ─────────────────────────────────────────────────

class TestCertificationTemplate:
    def test_create(self):
        ct = CertificationTemplate(cert_type="service", template="I certify...")
        assert ct.required is True
        assert ct.title is None


# ── Ruleset ────────────────────────────────────────────────────────────────

class TestRuleset:
    def test_minimal(self):
        rs = Ruleset(name="X", jurisdiction="wi", court_level="coa", document_type="brief")
        assert rs.page_limit is None
        assert rs.word_limit is None
        assert rs.allow_combined_case_facts is False

    def test_fixture(self, minimal_ruleset):
        assert minimal_ruleset.jurisdiction == "wisconsin"
        assert len(minimal_ruleset.heading_rules) == 4
        assert len(minimal_ruleset.section_rules) == 7


# ── Pattern models ─────────────────────────────────────────────────────────

class TestFontPattern:
    def test_create(self):
        fp = FontPattern(font_name="Times New Roman", font_size_pt=13.0)
        assert fp.frequency == 1
        assert fp.confidence == 1.0


class TestMarginPattern:
    def test_defaults(self):
        mp = MarginPattern()
        assert mp.top_inches == 1.0


class TestHeadingPattern:
    def test_create(self):
        hp = HeadingPattern(text="ARGUMENT", level=1, bold=True, all_caps=True)
        assert hp.all_caps


class TestSectionPattern:
    def test_create(self):
        sp = SectionPattern(section_type="arg", heading_text="Argument", order=7)
        assert sp.present is True


class TestFormatProfile:
    def test_defaults(self):
        fp = FormatProfile()
        assert fp.fonts == []
        assert fp.source_format == "unknown"
        assert fp.confidence == 1.0


class TestBriefAnalysis:
    def test_create(self):
        ba = BriefAnalysis(file_name="brief.docx")
        assert ba.tags == []
        assert ba.jurisdiction is None
