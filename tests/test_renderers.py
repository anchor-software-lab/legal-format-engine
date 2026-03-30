"""Tests for renderers (DOCX and Markdown)."""

from __future__ import annotations

import io
import pytest

from legal_format_engine.models.document import (
    ContentBlock,
    DocumentMetadata,
    DocumentModel,
    Section,
)
from legal_format_engine.models.caption import CaptionBlock
from legal_format_engine.models.section import HeadingLevel, HeadingRule, PageFormat, Ruleset
from legal_format_engine.renderers.markdown_renderer import render_markdown
from legal_format_engine.renderers.docx_renderer import render_docx


# ── Markdown Renderer ─────────────────────────────────────────────────────

class TestRenderMarkdown:
    def test_empty_document(self):
        doc = DocumentModel(metadata=DocumentMetadata())
        md = render_markdown(doc)
        assert md.strip() == ""

    def test_single_section(self):
        doc = DocumentModel(
            metadata=DocumentMetadata(),
            sections=[Section(
                section_type="arg", heading="Argument", heading_level=1,
                content=[ContentBlock(text="The court should reverse.", is_body_text=True)],
            )],
        )
        md = render_markdown(doc)
        assert "# Argument" in md
        assert "The court should reverse." in md

    def test_heading_levels(self):
        doc = DocumentModel(
            metadata=DocumentMetadata(),
            sections=[
                Section(section_type="", heading="Level 1", heading_level=1),
                Section(section_type="", heading="Level 2", heading_level=2),
                Section(section_type="", heading="Level 3", heading_level=3),
                Section(section_type="", heading="Level 4", heading_level=4),
            ],
        )
        md = render_markdown(doc)
        assert "# Level 1" in md
        assert "## Level 2" in md
        assert "### Level 3" in md
        assert "#### Level 4" in md

    def test_heading_level_capped_at_4(self):
        doc = DocumentModel(
            metadata=DocumentMetadata(),
            sections=[Section(section_type="", heading="Deep", heading_level=6)],
        )
        md = render_markdown(doc)
        assert "#### Deep" in md

    def test_bold_text(self):
        doc = DocumentModel(
            metadata=DocumentMetadata(),
            sections=[Section(
                section_type="", heading="H", heading_level=1,
                content=[ContentBlock(text="Important", bold=True)],
            )],
        )
        md = render_markdown(doc)
        assert "**Important**" in md

    def test_italic_text(self):
        doc = DocumentModel(
            metadata=DocumentMetadata(),
            sections=[Section(
                section_type="", heading="H", heading_level=1,
                content=[ContentBlock(text="Emphasis", italic=True)],
            )],
        )
        md = render_markdown(doc)
        assert "*Emphasis*" in md

    def test_numbering_prefix(self):
        doc = DocumentModel(
            metadata=DocumentMetadata(),
            sections=[Section(
                section_type="", heading="Point", heading_level=2,
                numbering_prefix="I.",
            )],
        )
        md = render_markdown(doc)
        assert "I. Point" in md

    def test_caption_rendered(self):
        caption = CaptionBlock(
            court_name="TEST COURT",
            case_number="123",
            document_title="Brief",
            lines=[
                ContentBlock(text="TEST COURT", bold=True, is_caption=True),
                ContentBlock(text="Case No. 123", is_caption=True),
            ],
        )
        doc = DocumentModel(metadata=DocumentMetadata(), caption=caption)
        md = render_markdown(doc)
        assert "**TEST COURT**" in md
        assert "Case No. 123" in md

    def test_certifications_rendered(self):
        cert = Section(
            section_type="cert", heading="Certification", heading_level=1,
            content=[ContentBlock(text="I certify...", is_body_text=True)],
        )
        doc = DocumentModel(metadata=DocumentMetadata(), certifications=[cert])
        md = render_markdown(doc)
        assert "Certification" in md
        assert "I certify..." in md

    def test_signature_block_rendered(self):
        sig = Section(
            section_type="sig", heading="", heading_level=0,
            content=[ContentBlock(text="Respectfully submitted,", is_body_text=True)],
        )
        doc = DocumentModel(metadata=DocumentMetadata(), signature_block=sig)
        md = render_markdown(doc)
        assert "Respectfully submitted," in md

    def test_subsections_rendered(self):
        parent = Section(
            section_type="", heading="Main", heading_level=1,
            subsections=[Section(section_type="", heading="Sub", heading_level=2)],
        )
        doc = DocumentModel(metadata=DocumentMetadata(), sections=[parent])
        md = render_markdown(doc)
        assert "# Main" in md
        assert "## Sub" in md

    def test_empty_content_block(self):
        doc = DocumentModel(
            metadata=DocumentMetadata(),
            sections=[Section(
                section_type="", heading="H", heading_level=1,
                content=[ContentBlock(text=""), ContentBlock(text="After blank")],
            )],
        )
        md = render_markdown(doc)
        assert "After blank" in md


# ── DOCX Renderer ─────────────────────────────────────────────────────────

class TestRenderDocx:
    def test_returns_bytes(self):
        doc = DocumentModel(metadata=DocumentMetadata())
        result = render_docx(doc)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_valid_docx_signature(self):
        doc = DocumentModel(metadata=DocumentMetadata())
        result = render_docx(doc)
        # DOCX is a ZIP file, starts with PK
        assert result[:2] == b"PK"

    def test_with_ruleset(self, minimal_ruleset):
        doc = DocumentModel(
            metadata=DocumentMetadata(),
            sections=[Section(
                section_type="arg", heading="Argument", heading_level=1,
                content=[ContentBlock(text="Test content.", is_body_text=True)],
            )],
        )
        result = render_docx(doc, minimal_ruleset)
        assert len(result) > 100

    def test_with_caption(self, minimal_ruleset):
        caption = CaptionBlock(
            court_name="TEST",
            case_number="123",
            document_title="Brief",
            lines=[
                ContentBlock(text="TEST COURT", bold=True, centered=True, is_caption=True),
            ],
        )
        doc = DocumentModel(metadata=DocumentMetadata(), caption=caption)
        result = render_docx(doc, minimal_ruleset)
        assert len(result) > 100

    def test_saves_to_file(self, tmp_dir, minimal_ruleset):
        doc = DocumentModel(metadata=DocumentMetadata())
        output_path = tmp_dir / "test.docx"
        result = render_docx(doc, minimal_ruleset, output_path=str(output_path))
        assert output_path.exists()
        assert output_path.read_bytes() == result

    def test_with_letterhead(self, minimal_ruleset):
        doc = DocumentModel(metadata=DocumentMetadata())
        letterhead = [
            {"text": "Law Firm Name", "bold": True, "font_size_pt": 14, "alignment": "center"},
            {"text": "123 Main St", "font_size_pt": 10, "alignment": "center"},
        ]
        result = render_docx(doc, minimal_ruleset, letterhead_lines=letterhead)
        assert len(result) > 100

    def test_without_ruleset(self):
        doc = DocumentModel(
            metadata=DocumentMetadata(),
            sections=[Section(
                section_type="", heading="Test", heading_level=1,
                content=[ContentBlock(text="Content", is_body_text=True)],
            )],
        )
        result = render_docx(doc)
        assert isinstance(result, bytes)

    def test_page_break_block(self, minimal_ruleset):
        doc = DocumentModel(
            metadata=DocumentMetadata(),
            sections=[Section(
                section_type="", heading="H", heading_level=1,
                content=[
                    ContentBlock(text="Before break", is_body_text=True),
                    ContentBlock(text="", is_page_break=True),
                    ContentBlock(text="After break", is_body_text=True),
                ],
            )],
        )
        result = render_docx(doc, minimal_ruleset)
        assert len(result) > 100

    def test_certifications_rendered(self, minimal_ruleset):
        doc = DocumentModel(
            metadata=DocumentMetadata(),
            certifications=[Section(
                section_type="cert", heading="Certification", heading_level=1,
                content=[ContentBlock(text="I certify...", is_body_text=True)],
            )],
        )
        result = render_docx(doc, minimal_ruleset)
        assert len(result) > 100

    def test_signature_block_rendered(self, minimal_ruleset):
        doc = DocumentModel(
            metadata=DocumentMetadata(),
            signature_block=Section(
                section_type="sig", heading="", heading_level=0,
                content=[ContentBlock(text="Signed", is_body_text=True)],
            ),
        )
        result = render_docx(doc, minimal_ruleset)
        assert len(result) > 100

    def test_subsections(self, minimal_ruleset):
        doc = DocumentModel(
            metadata=DocumentMetadata(),
            sections=[Section(
                section_type="", heading="Parent", heading_level=1,
                subsections=[Section(
                    section_type="", heading="Child", heading_level=2,
                    content=[ContentBlock(text="Sub content", is_body_text=True)],
                )],
            )],
        )
        result = render_docx(doc, minimal_ruleset)
        assert len(result) > 100

    def test_horizontal_rule_in_caption(self, minimal_ruleset):
        caption = CaptionBlock(
            court_name="X",
            case_number="1",
            document_title="Brief",
            lines=[ContentBlock(text="\u2500" * 50, centered=True, is_caption=True)],
        )
        doc = DocumentModel(metadata=DocumentMetadata(), caption=caption)
        result = render_docx(doc, minimal_ruleset)
        assert len(result) > 100

    def test_letterhead_alignments(self, minimal_ruleset):
        doc = DocumentModel(metadata=DocumentMetadata())
        letterhead = [
            {"text": "Left", "alignment": "left"},
            {"text": "Center", "alignment": "center"},
            {"text": "Right", "alignment": "right"},
        ]
        result = render_docx(doc, minimal_ruleset, letterhead_lines=letterhead)
        assert len(result) > 100
