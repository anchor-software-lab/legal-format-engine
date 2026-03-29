"""Edge case tests for all engines."""

import pytest

from legal_format_engine.engines.caption_engine import generate_caption
from legal_format_engine.engines.heading_engine import normalize_headings, normalize_single_heading
from legal_format_engine.engines.section_engine import (
    insert_missing_sections,
    reorder_sections,
    validate_sections,
)
from legal_format_engine.engines.boilerplate_engine import (
    generate_certifications,
    generate_signature_block,
)
from legal_format_engine.engines.citation_engine import (
    CitationType,
    check_citation_consistency,
    check_document_citations,
)
from legal_format_engine.models.document import (
    ContentBlock,
    HeadingLevel,
    LegalDocument,
    Section,
    Severity,
)
from legal_format_engine.models.metadata import (
    AttorneyInfo,
    CaseMetadata,
    DocumentMetadata,
    Party,
    PartyRole,
)
from legal_format_engine.rules.loader import load_ruleset
from legal_format_engine.rules.schema import CaptionRule, HeadingRule


def _make_meta(**kwargs):
    parties = kwargs.get("parties", [
        Party(name="State of Wisconsin", role=PartyRole.PLAINTIFF_RESPONDENT),
        Party(name="John Smith", role=PartyRole.DEFENDANT_APPELLANT),
    ])
    return DocumentMetadata(
        jurisdiction="wisconsin",
        court_level="appellate",
        document_type="brief",
        case=CaseMetadata(
            case_number=kwargs.get("case_number", "2025AP001234-CR"),
            court_name=kwargs.get("court_name", "Court of Appeals"),
            district=kwargs.get("district", "District II"),
            county_of_origin=kwargs.get("county", "Dane"),
            judge_name=kwargs.get("judge", "Hon. Smith"),
            parties=parties,
        ),
        attorney=AttorneyInfo(
            name=kwargs.get("attorney_name", "Jane Doe"),
            bar_number=kwargs.get("bar_number", "1234567"),
            firm=kwargs.get("firm", "Test Firm"),
            address=kwargs.get("address", "123 Main St"),
            phone=kwargs.get("phone", "(608) 555-1234"),
            email=kwargs.get("email", "jane@test.com"),
        ),
        document_title=kwargs.get("title", "Brief of Defendant-Appellant"),
    )


# ── Caption Engine Edge Cases ──────────────────────────────────────


class TestCaptionEdgeCases:
    def test_no_parties(self, wi_appellate_ruleset):
        meta = _make_meta(parties=[])
        caption = generate_caption(meta, wi_appellate_ruleset.caption_rule)
        assert len(caption.lines) > 0

    def test_single_party(self, wi_appellate_ruleset):
        meta = _make_meta(parties=[
            Party(name="State of Wisconsin", role=PartyRole.PLAINTIFF_RESPONDENT),
        ])
        caption = generate_caption(meta, wi_appellate_ruleset.caption_rule)
        assert any("WISCONSIN" in line.text for line in caption.lines)

    def test_three_parties(self, wi_appellate_ruleset):
        meta = _make_meta(parties=[
            Party(name="State of Wisconsin", role=PartyRole.PLAINTIFF_RESPONDENT),
            Party(name="John Smith", role=PartyRole.DEFENDANT_APPELLANT),
            Party(name="Jane Doe", role=PartyRole.RESPONDENT),
        ])
        caption = generate_caption(meta, wi_appellate_ruleset.caption_rule)
        assert len(caption.lines) > 0

    def test_very_long_case_number(self, wi_appellate_ruleset):
        meta = _make_meta(case_number="2025AP001234-CR-EXTENDED-NUMBER")
        caption = generate_caption(meta, wi_appellate_ruleset.caption_rule)
        assert any("2025AP001234" in line.text for line in caption.lines)

    def test_apostrophe_in_party_name(self, wi_appellate_ruleset):
        meta = _make_meta(parties=[
            Party(name="State of Wisconsin", role=PartyRole.PLAINTIFF_RESPONDENT),
            Party(name="Patrick O'Brien", role=PartyRole.DEFENDANT_APPELLANT),
        ])
        caption = generate_caption(meta, wi_appellate_ruleset.caption_rule)
        assert any("O'BRIEN" in line.text.upper() for line in caption.lines)

    def test_hyphenated_party_name(self, wi_appellate_ruleset):
        meta = _make_meta(parties=[
            Party(name="State of Wisconsin", role=PartyRole.PLAINTIFF_RESPONDENT),
            Party(name="Mary Smith-Jones", role=PartyRole.DEFENDANT_APPELLANT),
        ])
        caption = generate_caption(meta, wi_appellate_ruleset.caption_rule)
        assert any("SMITH-JONES" in line.text.upper() for line in caption.lines)

    def test_empty_document_title(self, wi_appellate_ruleset):
        meta = _make_meta(title="")
        caption = generate_caption(meta, wi_appellate_ruleset.caption_rule)
        assert len(caption.lines) > 0

    def test_no_district(self, wi_appellate_ruleset):
        meta = _make_meta(district=None)
        caption = generate_caption(meta, wi_appellate_ruleset.caption_rule)
        assert len(caption.lines) > 0

    def test_no_county(self, wi_appellate_ruleset):
        meta = _make_meta(county=None)
        caption = generate_caption(meta, wi_appellate_ruleset.caption_rule)
        assert len(caption.lines) > 0


# ── Heading Engine Edge Cases ──────────────────────────────────────


class TestHeadingEdgeCases:
    def test_empty_heading_text(self, wi_appellate_ruleset):
        sections = [
            Section(id="empty", heading_text="",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
        ]
        result = normalize_headings(sections, wi_appellate_ruleset)
        assert len(result) == 1

    def test_very_long_heading(self):
        rule = HeadingRule(level=2, case_style="title", alignment="left", numbering="roman")
        long_text = "This Is A Very Long Heading That Goes On And On " * 5
        text, prefix = normalize_single_heading(long_text, rule, index=0)
        assert isinstance(text, str)
        assert prefix == "I."

    def test_heading_with_legal_section(self):
        rule = HeadingRule(level=2, case_style="upper", alignment="left", numbering="roman")
        text, prefix = normalize_single_heading("Standard Under § 904.04", rule, index=0)
        assert "904.04" in text

    def test_heading_with_numbers(self):
        rule = HeadingRule(level=2, case_style="title", alignment="left", numbering="roman")
        text, prefix = normalize_single_heading("rule 802.04 analysis", rule, index=0)
        assert "802.04" in text

    def test_no_sections(self, wi_appellate_ruleset):
        result = normalize_headings([], wi_appellate_ruleset)
        assert result == []

    def test_mixed_levels(self, wi_appellate_ruleset):
        sections = [
            Section(id="l1", heading_text="argument",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
            Section(id="l2", heading_text="first point",
                    heading_level=HeadingLevel.LEVEL_2, content=[]),
            Section(id="l3", heading_text="sub-point",
                    heading_level=HeadingLevel.LEVEL_3, content=[]),
            Section(id="l4", heading_text="detail",
                    heading_level=HeadingLevel.LEVEL_4, content=[]),
        ]
        result = normalize_headings(sections, wi_appellate_ruleset)
        assert len(result) == 4
        assert result[0].heading_text == "Argument"


# ── Section Engine Edge Cases ──────────────────────────────────────


class TestSectionValidationEdgeCases:
    def test_empty_document(self, wi_appellate_ruleset):
        doc = LegalDocument(sections=[])
        doc = validate_sections(doc, wi_appellate_ruleset)
        missing = [i for i in doc.issues if i.code == "MISSING_SECTION"]
        assert len(missing) > 0

    def test_all_unknown_sections(self, wi_appellate_ruleset):
        doc = LegalDocument(sections=[
            Section(id="custom1", heading_text="PRELIMINARY STATEMENT",
                    heading_level=HeadingLevel.LEVEL_1, content=[ContentBlock(text="Text.")]),
            Section(id="custom2", heading_text="MISCELLANEOUS APPENDIX",
                    heading_level=HeadingLevel.LEVEL_1, content=[ContentBlock(text="Text.")]),
        ])
        doc = validate_sections(doc, wi_appellate_ruleset)
        unknown = [i for i in doc.issues if i.code == "UNKNOWN_SECTION"]
        assert len(unknown) >= 2

    def test_duplicate_matched_sections(self, wi_appellate_ruleset):
        doc = LegalDocument(sections=[
            Section(id="arg1", heading_text="ARGUMENT",
                    heading_level=HeadingLevel.LEVEL_1, content=[ContentBlock(text="First.")]),
            Section(id="arg2", heading_text="ARGUMENT",
                    heading_level=HeadingLevel.LEVEL_1, content=[ContentBlock(text="Second.")]),
        ])
        doc = validate_sections(doc, wi_appellate_ruleset)
        assert isinstance(doc.issues, list)

    def test_reorder_already_correct(self, wi_appellate_ruleset):
        doc = LegalDocument(sections=[
            Section(id="issues", heading_text="STATEMENT OF ISSUES",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
            Section(id="arg", heading_text="ARGUMENT",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
            Section(id="conc", heading_text="CONCLUSION",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
        ])
        doc = reorder_sections(doc, wi_appellate_ruleset)
        headings = [s.heading_text for s in doc.sections]
        assert headings.index("STATEMENT OF ISSUES") < headings.index("ARGUMENT")
        assert headings.index("ARGUMENT") < headings.index("CONCLUSION")

    def test_reorder_reverse_order(self, wi_appellate_ruleset):
        doc = LegalDocument(sections=[
            Section(id="conc", heading_text="CONCLUSION",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
            Section(id="arg", heading_text="ARGUMENT",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
            Section(id="issues", heading_text="STATEMENT OF ISSUES",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
        ])
        doc = reorder_sections(doc, wi_appellate_ruleset)
        headings = [s.heading_text for s in doc.sections]
        assert headings.index("STATEMENT OF ISSUES") < headings.index("ARGUMENT")
        assert headings.index("ARGUMENT") < headings.index("CONCLUSION")

    def test_reorder_only_unmatched(self, wi_appellate_ruleset):
        doc = LegalDocument(sections=[
            Section(id="a", heading_text="BACKGROUND",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
            Section(id="b", heading_text="OVERVIEW",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
        ])
        doc = reorder_sections(doc, wi_appellate_ruleset)
        assert len(doc.sections) == 2

    def test_insert_missing_at_correct_position(self, wi_appellate_ruleset):
        doc = LegalDocument(sections=[
            Section(id="arg", heading_text="ARGUMENT",
                    heading_level=HeadingLevel.LEVEL_1, content=[]),
        ])
        doc = insert_missing_sections(doc, wi_appellate_ruleset)
        headings = [s.heading_text for s in doc.sections]
        issues_idx = next(
            (i for i, h in enumerate(headings) if "ISSUES" in h.upper()), None
        )
        arg_idx = next(
            (i for i, h in enumerate(headings) if h == "ARGUMENT"), None
        )
        if issues_idx is not None and arg_idx is not None:
            assert issues_idx < arg_idx


# ── Citation Engine Edge Cases ─────────────────────────────────────


class TestCitationEdgeCases:
    def test_empty_text(self):
        report = check_citation_consistency("")
        assert report.citations == []
        assert report.issues == []

    def test_no_citations(self):
        text = "The court erred. The defendant should prevail."
        report = check_citation_consistency(text)
        cases = [c for c in report.citations if c.citation_type == CitationType.CASE]
        assert len(cases) == 0

    def test_multiple_citations_one_sentence(self):
        text = (
            "See State v. Sullivan, 216 Wis. 2d 768 (1998); "
            "State v. Normington, 306 Wis. 2d 727 (2008)."
        )
        report = check_citation_consistency(text)
        cases = [c for c in report.citations if c.citation_type == CitationType.CASE]
        assert len(cases) >= 1

    def test_id_at_start_of_sentence(self):
        text = "The court ruled. Id. at 456. The reasoning was clear."
        report = check_citation_consistency(text)
        ids = [c for c in report.citations if c.citation_type == CitationType.ID]
        assert len(ids) == 1

    def test_many_id_references(self):
        text = ". ".join([f"Point {i}. Id. at {100 + i}" for i in range(20)])
        report = check_citation_consistency(text)
        ids = [c for c in report.citations if c.citation_type == CitationType.ID]
        assert len(ids) >= 15

    def test_pin_cite_range(self):
        text = "State v. Smith, 123 Wis. 2d 456, 460-65 (2020)"
        report = check_citation_consistency(text)
        cases = [c for c in report.citations if c.citation_type == CitationType.CASE]
        assert len(cases) >= 1

    def test_wi_stat_rule_short_form(self):
        text = "under s. 809.19(8)(b) and s. 904.04(2)(a)"
        report = check_citation_consistency(text)
        assert len(report.statute_citations) >= 2

    def test_section_symbol_without_space(self):
        text = "under §904.04(2)"
        report = check_citation_consistency(text)
        issues = [i for i in report.issues if i.code == "SECTION_SYMBOL_SPACING"]
        assert len(issues) >= 1

    def test_cross_section_document(self):
        sections = [
            {"id": "facts", "text": "State v. Sullivan, 216 Wis. 2d 768 (1998)."},
            {"id": "argument", "text": "Sullivan, 216 Wis. 2d at 774. Id. at 780."},
        ]
        report = check_document_citations(sections)
        assert len(report.citations) >= 2


# ── Boilerplate Engine Edge Cases ──────────────────────────────────


class TestBoilerplateEdgeCases:
    def test_signature_no_firm(self):
        meta = _make_meta(firm=None)
        sig = generate_signature_block(meta)
        assert "Jane Doe" in sig.attorney_name

    def test_signature_special_chars_in_name(self):
        meta = _make_meta(attorney_name="María O'Connor-López")
        sig = generate_signature_block(meta)
        assert "O'Connor" in sig.attorney_name

    def test_certifications_zero_word_count(self, wi_appellate_ruleset):
        meta = _make_meta()
        certs = generate_certifications(meta, wi_appellate_ruleset.certifications, word_count=0)
        assert len(certs) > 0

    def test_certifications_large_word_count(self, wi_appellate_ruleset):
        meta = _make_meta()
        certs = generate_certifications(
            meta, wi_appellate_ruleset.certifications, word_count=50000
        )
        cert_text = "\n".join(
            s.heading_text + " " + " ".join(b.text for b in s.content) for s in certs
        )
        assert "50000" in cert_text or "50,000" in cert_text

    def test_certifications_no_word_count(self, wi_appellate_ruleset):
        meta = _make_meta()
        certs = generate_certifications(meta, wi_appellate_ruleset.certifications)
        assert len(certs) > 0
