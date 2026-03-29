"""DOCX renderer for legal documents.

Produces properly formatted Word documents from the internal
LegalDocument representation using python-docx.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document as DocxDocument
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.shared import Inches, Pt, RGBColor

from legal_format_engine.models.document import (
    Alignment,
    CaptionBlock,
    ContentBlock,
    LegalDocument,
    Section,
    SignatureBlock,
)
from legal_format_engine.models.letterhead import Letterhead, LetterheadLine
from legal_format_engine.rules.schema import PageFormat, Ruleset

# Alignment mapping
_ALIGN_MAP = {
    Alignment.LEFT: WD_ALIGN_PARAGRAPH.LEFT,
    Alignment.CENTER: WD_ALIGN_PARAGRAPH.CENTER,
    Alignment.RIGHT: WD_ALIGN_PARAGRAPH.RIGHT,
    Alignment.JUSTIFY: WD_ALIGN_PARAGRAPH.JUSTIFY,
}


def render_docx(
    doc: LegalDocument,
    ruleset: Ruleset,
    output_path: str | Path,
    letterhead: Letterhead | None = None,
) -> Path:
    """Render a LegalDocument to a DOCX file.

    Args:
        doc: The internal document representation.
        ruleset: The active ruleset for formatting rules.
        output_path: Where to save the DOCX file.
        letterhead: Optional letterhead to render at the top of the document.

    Returns:
        The Path to the saved file.
    """
    output_path = Path(output_path)
    docx = DocxDocument()
    fmt = ruleset.page_format

    _setup_page(docx, fmt)
    _set_default_font(docx, fmt)

    if letterhead:
        _render_letterhead(docx, letterhead, fmt)

    if doc.caption:
        _render_caption(docx, doc.caption, fmt)
        _add_blank_line(docx, fmt)

    for section in doc.sections:
        _render_section(docx, section, fmt, ruleset)

    if doc.signature_block:
        _add_blank_line(docx, fmt)
        _render_signature_block(docx, doc.signature_block, fmt)

    for cert in doc.certifications:
        docx.add_page_break()
        _render_section(docx, cert, fmt, ruleset)

    docx.save(str(output_path))
    return output_path


def _setup_page(docx: DocxDocument, fmt: PageFormat) -> None:
    """Configure page dimensions and margins."""
    section = docx.sections[0]
    section.page_width = Inches(fmt.page_width_inches)
    section.page_height = Inches(fmt.page_height_inches)
    section.top_margin = Inches(fmt.margin_top_inches)
    section.bottom_margin = Inches(fmt.margin_bottom_inches)
    section.left_margin = Inches(fmt.margin_left_inches)
    section.right_margin = Inches(fmt.margin_right_inches)
    section.orientation = WD_ORIENT.PORTRAIT


def _set_default_font(docx: DocxDocument, fmt: PageFormat) -> None:
    """Set the default font for the document."""
    style = docx.styles["Normal"]
    font = style.font
    font.name = fmt.font_name
    font.size = Pt(fmt.font_size_pt)
    pf = style.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.DOUBLE
    pf.space_after = Pt(0)
    pf.space_before = Pt(0)


def _render_caption(docx: DocxDocument, caption: CaptionBlock, fmt: PageFormat) -> None:
    """Render the caption block."""
    for line in caption.lines:
        _add_content_paragraph(docx, line, fmt)


def _render_section(
    docx: DocxDocument,
    section: Section,
    fmt: PageFormat,
    ruleset: Ruleset,
) -> None:
    """Render a section with its heading and content."""
    if section.heading_text:
        heading_rule = ruleset.get_heading_rule(section.heading_level)
        heading_bold = heading_rule.bold if heading_rule else True

        # Build full heading text with prefix
        heading_text = section.heading_text
        if section.numbering_prefix:
            heading_text = f"{section.numbering_prefix} {heading_text}"

        alignment = Alignment.CENTER
        if heading_rule:
            alignment = Alignment(heading_rule.alignment)

        heading_block = ContentBlock(
            text=heading_text,
            bold=heading_bold,
            alignment=alignment,
        )
        _add_content_paragraph(docx, heading_block, fmt)

    for block in section.content:
        _add_content_paragraph(docx, block, fmt)

    for subsection in section.subsections:
        _render_section(docx, subsection, fmt, ruleset)


def _render_signature_block(
    docx: DocxDocument,
    sig: SignatureBlock,
    fmt: PageFormat,
) -> None:
    """Render the attorney signature block."""
    lines = [
        "Respectfully submitted,",
        "",
        "____________________________",
        sig.attorney_name,
        f"State Bar No. {sig.bar_number}",
    ]
    if sig.firm:
        lines.append(sig.firm)
    lines.extend([
        sig.address,
        f"Phone: {sig.phone}",
        f"Email: {sig.email}",
    ])

    for text in lines:
        block = ContentBlock(text=text, alignment=Alignment.LEFT)
        _add_content_paragraph(docx, block, fmt)


def _add_content_paragraph(
    docx: DocxDocument,
    block: ContentBlock,
    fmt: PageFormat,
) -> None:
    """Add a single content block as a paragraph."""
    para = docx.add_paragraph()
    para.alignment = _ALIGN_MAP.get(block.alignment, WD_ALIGN_PARAGRAPH.JUSTIFY)

    run = para.add_run(block.text)
    run.font.name = fmt.font_name
    run.font.size = Pt(fmt.font_size_pt)
    run.bold = block.bold
    run.italic = block.italic
    run.underline = block.underline


def _add_blank_line(docx: DocxDocument, fmt: PageFormat) -> None:
    """Add a blank paragraph as a spacer."""
    para = docx.add_paragraph()
    run = para.add_run("")
    run.font.name = fmt.font_name
    run.font.size = Pt(fmt.font_size_pt)


# ── Letterhead ────────────────────────────────────────────────────────

_LETTERHEAD_ALIGN = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
}


def _render_letterhead(docx: DocxDocument, lh: Letterhead, fmt: PageFormat) -> None:
    """Render a letterhead at the top of the document."""
    # Logo (if present)
    if lh.logo_path:
        logo = Path(lh.logo_path)
        if logo.exists():
            para = docx.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = para.add_run()
            run.add_picture(str(logo), width=Inches(lh.logo_width_inches))

    # Text lines
    for line in lh.lines:
        _render_letterhead_line(docx, line, fmt)

    # Separator
    if lh.separator_line:
        para = docx.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        # Use a bottom border on the paragraph
        pf = para.paragraph_format
        pf.space_before = Pt(4)
        pf.space_after = Pt(lh.spacing_after_pt)
        run = para.add_run("_" * 60)
        run.font.size = Pt(6)
        run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
    else:
        # Just add spacing
        para = docx.add_paragraph()
        para.paragraph_format.space_after = Pt(lh.spacing_after_pt)


def _render_letterhead_line(
    docx: DocxDocument, line: LetterheadLine, fmt: PageFormat
) -> None:
    """Render a single letterhead line."""
    para = docx.add_paragraph()
    para.alignment = _LETTERHEAD_ALIGN.get(line.alignment, WD_ALIGN_PARAGRAPH.CENTER)

    # Tight spacing for letterhead
    pf = para.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.line_spacing_rule = WD_LINE_SPACING.SINGLE

    run = para.add_run(line.text)
    run.font.name = fmt.font_name
    run.font.size = Pt(line.font_size_pt or fmt.font_size_pt)
    run.bold = line.bold
    run.italic = line.italic
