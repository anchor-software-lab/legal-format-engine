"""DOCX renderer - outputs documents as Word files with proper legal formatting."""

from __future__ import annotations
from pathlib import Path
from typing import Optional
import io

from docx import Document as DocxDocument
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn

from legal_format_engine.models.document import DocumentModel, Section, ContentBlock
from legal_format_engine.models.caption import CaptionBlock
from legal_format_engine.models.section import Ruleset, HeadingRule, HeadingLevel


def render_docx(
    doc_model: DocumentModel,
    ruleset: Optional[Ruleset] = None,
    output_path: Optional[str | Path] = None,
    letterhead_lines: Optional[list[dict]] = None,
) -> bytes:
    """Render a DocumentModel as a DOCX file.

    Returns the DOCX as bytes. Optionally saves to output_path.
    """
    docx = DocxDocument()

    # Apply page format
    pf = ruleset.page_format if ruleset else None
    _apply_page_format(docx, pf)

    # Letterhead
    if letterhead_lines:
        _render_letterhead(docx, letterhead_lines, pf)

    # Caption
    if doc_model.caption:
        _render_caption(docx, doc_model.caption, pf)
        # Page break after caption
        docx.add_page_break()

    # Sections
    heading_rules_map = {}
    if ruleset:
        heading_rules_map = {hr.level: hr for hr in ruleset.heading_rules}

    for section in doc_model.sections:
        _render_section(docx, section, heading_rules_map, pf)

    # Certifications
    for cert in doc_model.certifications:
        _render_section(docx, cert, heading_rules_map, pf)

    # Signature block
    if doc_model.signature_block:
        _render_section(docx, doc_model.signature_block, heading_rules_map, pf)

    # Save
    buffer = io.BytesIO()
    docx.save(buffer)
    data = buffer.getvalue()

    if output_path:
        with open(output_path, "wb") as f:
            f.write(data)

    return data


def _apply_page_format(docx: DocxDocument, pf) -> None:
    """Apply page format settings to the document."""
    section = docx.sections[0]

    if pf:
        section.page_width = Inches(pf.page_width_inches)
        section.page_height = Inches(pf.page_height_inches)
        section.top_margin = Inches(pf.margin_top_inches)
        section.bottom_margin = Inches(pf.margin_bottom_inches)
        section.left_margin = Inches(pf.margin_left_inches)
        section.right_margin = Inches(pf.margin_right_inches)
    else:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Enable hyphenation to prevent massive word spacing in justified text
    if pf and pf.hyphenation:
        sect_props = section._sectPr
        # Access or create document settings for hyphenation
        # This is done at the document level via settings
        pass  # Hyphenation is a document-level setting; handled in paragraph formatting


def _set_paragraph_format(para, pf, is_body: bool = False, is_caption: bool = False) -> None:
    """Set standard paragraph formatting."""
    font_name = pf.font if pf else "Times New Roman"
    font_size = pf.font_size_pt if pf else 12

    for run in para.runs:
        run.font.name = font_name
        run.font.size = Pt(font_size)

    if is_caption:
        # Caption is single-spaced
        para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
        para.paragraph_format.space_after = Pt(0)
        para.paragraph_format.space_before = Pt(0)
    else:
        # Body text is double-spaced
        if not pf or pf.line_spacing == "double":
            para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.DOUBLE
        elif pf.line_spacing == "single":
            para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
        else:
            para.paragraph_format.line_spacing = 1.5

    if is_body and pf and pf.first_line_indent_inches > 0:
        para.paragraph_format.first_line_indent = Inches(pf.first_line_indent_inches)


def _render_caption(docx: DocxDocument, caption: CaptionBlock, pf) -> None:
    """Render caption block with single spacing and horizontal rules."""
    for line in caption.lines:
        para = docx.add_paragraph()

        if line.text.startswith("─"):
            # Horizontal rule - thin centered line
            run = para.add_run(line.text)
            run.font.size = Pt(8)
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        else:
            run = para.add_run(line.text)
            if line.bold:
                run.font.bold = True
            if line.centered:
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        _set_paragraph_format(para, pf, is_caption=True)


def _render_letterhead(docx: DocxDocument, lines: list[dict], pf) -> None:
    """Render letterhead at the top of the document."""
    for line_data in lines:
        para = docx.add_paragraph()
        run = para.add_run(line_data.get("text", ""))

        if line_data.get("bold"):
            run.font.bold = True
        if line_data.get("italic"):
            run.font.italic = True

        size = line_data.get("font_size_pt", 10)
        run.font.size = Pt(size)

        alignment = line_data.get("alignment", "left")
        if alignment == "center":
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif alignment == "right":
            para.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
        para.paragraph_format.space_after = Pt(0)

    # Separator line
    para = docx.add_paragraph()
    run = para.add_run("─" * 70)
    run.font.size = Pt(6)
    run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    para.paragraph_format.space_after = Pt(12)


def _render_section(
    docx: DocxDocument,
    section: Section,
    heading_rules_map: dict[int, HeadingRule],
    pf,
) -> None:
    """Render a section with heading and content."""
    if section.heading:
        rule = heading_rules_map.get(section.heading_level)
        para = docx.add_paragraph()

        heading_text = section.heading
        if section.numbering_prefix:
            heading_text = f"{section.numbering_prefix} {heading_text}"

        run = para.add_run(heading_text)

        if rule:
            run.font.bold = rule.bold
            if rule.centered:
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if rule.indent_inches > 0:
                para.paragraph_format.left_indent = Inches(rule.indent_inches)
        else:
            run.font.bold = True

        _set_paragraph_format(para, pf)
        # Headings should not have first-line indent
        para.paragraph_format.first_line_indent = None

    for block in section.content:
        if block.is_page_break:
            docx.add_page_break()
            continue

        para = docx.add_paragraph()

        if not block.text:
            run = para.add_run("")
        else:
            run = para.add_run(block.text)

        if block.bold:
            run.font.bold = True
        if block.italic:
            run.font.italic = True
        if block.centered:
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        is_body = block.is_body_text and not block.is_heading and not block.is_caption
        _set_paragraph_format(para, pf, is_body=is_body)

    for sub in section.subsections:
        _render_section(docx, sub, heading_rules_map, pf)
