"""Tests for pipeline.py - full integration pipeline."""

from __future__ import annotations

import pytest

from legal_format_engine.pipeline import (
    format_and_render_docx,
    format_and_render_markdown,
    format_document,
    validate_document,
)
from legal_format_engine.models.document import (
    Attorney,
    CaseMetadata,
    DocumentMetadata,
    Party,
    PartyRole,
)


class TestFormatDocument:
    def test_basic_format(self, sample_brief_text):
        doc = format_document(sample_brief_text)
        assert doc is not None
        assert len(doc.sections) >= 1

    def test_sections_reordered(self, sample_brief_text):
        doc = format_document(sample_brief_text)
        # Sections should be in ruleset order
        headings = [s.heading for s in doc.sections]
        # Table of Contents before Argument
        if "Table of Contents" in headings and "Argument" in headings:
            assert headings.index("Table of Contents") < headings.index("Argument")

    def test_headings_normalized(self, sample_brief_text):
        doc = format_document(sample_brief_text)
        # Level 1 headings should be title case (per Wisconsin ruleset)
        for s in doc.sections:
            if s.heading_level == 1 and s.heading:
                # Should not be ALL CAPS anymore
                assert s.heading != s.heading.upper() or len(s.heading) <= 3

    def test_missing_sections_inserted(self, sample_brief_text):
        doc = format_document(sample_brief_text, insert_missing=True)
        headings = [s.heading for s in doc.sections]
        # Some stub sections might be inserted
        assert len(doc.sections) >= 5

    def test_no_missing_sections_inserted(self, sample_brief_text):
        doc = format_document(sample_brief_text, insert_missing=False)
        stubs = [s for s in doc.sections if s.is_stub]
        assert len(stubs) == 0

    def test_with_case_meta(self, sample_brief_text, sample_case_meta):
        doc = format_document(sample_brief_text, case_meta=sample_case_meta)
        assert doc.caption is not None
        assert doc.case_metadata is not None
        assert "2025AP001234" in doc.caption.case_number

    def test_with_attorney(self, sample_brief_text, sample_attorney):
        doc = format_document(sample_brief_text, attorney=sample_attorney)
        assert doc.signature_block is not None
        assert len(doc.certifications) >= 1

    def test_with_word_count(self, sample_brief_text, sample_attorney):
        doc = format_document(sample_brief_text, attorney=sample_attorney, word_count=9500)
        cert_texts = " ".join(
            b.text for c in doc.certifications for b in c.content
        )
        assert "9500" in cert_texts

    def test_custom_metadata(self, sample_brief_text):
        meta = DocumentMetadata(
            jurisdiction="wisconsin",
            document_type="appellate_brief",
            document_title="Reply Brief",
        )
        doc = format_document(sample_brief_text, doc_meta=meta)
        assert doc.metadata.document_title == "Reply Brief"

    def test_caption_with_title(self, sample_brief_text, sample_case_meta):
        meta = DocumentMetadata(document_title="Opening Brief")
        doc = format_document(sample_brief_text, case_meta=sample_case_meta, doc_meta=meta)
        assert doc.caption.document_title == "Opening Brief"


class TestFormatAndRenderMarkdown:
    def test_returns_string(self, sample_brief_text):
        md = format_and_render_markdown(sample_brief_text)
        assert isinstance(md, str)
        assert len(md) > 0

    def test_contains_headings(self, sample_brief_text):
        md = format_and_render_markdown(sample_brief_text)
        assert "#" in md

    def test_with_all_options(self, sample_brief_text, sample_case_meta, sample_attorney):
        md = format_and_render_markdown(
            sample_brief_text,
            case_meta=sample_case_meta,
            attorney=sample_attorney,
            word_count=8000,
        )
        assert "Alice Advocate" in md
        assert len(md) > 100


class TestFormatAndRenderDocx:
    def test_returns_bytes(self, sample_brief_text):
        result = format_and_render_docx(sample_brief_text)
        assert isinstance(result, bytes)
        assert result[:2] == b"PK"

    def test_saves_to_file(self, sample_brief_text, tmp_dir):
        output = tmp_dir / "test.docx"
        result = format_and_render_docx(sample_brief_text, output_path=str(output))
        assert output.exists()

    def test_with_letterhead(self, sample_brief_text):
        letterhead = [{"text": "Law Firm", "bold": True, "font_size_pt": 14, "alignment": "center"}]
        result = format_and_render_docx(sample_brief_text, letterhead_lines=letterhead)
        assert len(result) > 100


class TestValidateDocument:
    def test_returns_issues(self, sample_brief_text):
        issues = validate_document(sample_brief_text)
        assert isinstance(issues, list)

    def test_complete_brief_few_errors(self, sample_brief_text):
        issues = validate_document(sample_brief_text)
        errors = [i for i in issues if i.severity == "error"]
        # A well-formed brief should have minimal errors
        # (may still have some missing sections like TOA)
        assert len(errors) < 10

    def test_empty_text_many_issues(self):
        issues = validate_document("")
        assert len(issues) >= 1

    def test_custom_jurisdiction(self, sample_brief_text):
        # Should still work with default jurisdiction
        issues = validate_document(sample_brief_text, DocumentMetadata())
        assert isinstance(issues, list)

    def test_issue_dict_format(self, sample_brief_text):
        issues = validate_document(sample_brief_text)
        for issue in issues:
            d = issue.to_dict()
            assert "code" in d
            assert "severity" in d
            assert "message" in d
