"""DOCX parser - reads Word documents into structured document model."""

from __future__ import annotations
from pathlib import Path
from typing import Optional

from docx import Document as DocxDocument
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

from legal_format_engine.models.document import ContentBlock, DocumentModel, DocumentMetadata, Section
from legal_format_engine.models.patterns import FormatProfile, FontPattern, MarginPattern, HeadingPattern


def parse_docx(
    file_path: str | Path,
    metadata: Optional[DocumentMetadata] = None,
) -> DocumentModel:
    """Parse a DOCX file into a structured DocumentModel."""
    if metadata is None:
        metadata = DocumentMetadata()

    doc = DocxDocument(str(file_path))
    sections: list[Section] = []
    current_heading = ""
    current_level = 1
    current_content: list[ContentBlock] = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            if current_content:
                current_content.append(ContentBlock(text=""))
            continue

        is_heading = _is_heading_style(para)
        if is_heading:
            if current_heading or current_content:
                sections.append(Section(
                    section_type="",
                    heading=current_heading,
                    heading_level=current_level,
                    content=current_content,
                ))
            current_heading = text
            current_level = _get_heading_level(para)
            current_content = []
        else:
            block = _para_to_content_block(para)
            current_content.append(block)

    if current_heading or current_content:
        sections.append(Section(
            section_type="",
            heading=current_heading,
            heading_level=current_level,
            content=current_content,
        ))

    return DocumentModel(metadata=metadata, sections=sections)


def parse_docx_bytes(
    data: bytes,
    metadata: Optional[DocumentMetadata] = None,
) -> DocumentModel:
    """Parse DOCX from bytes."""
    import io
    if metadata is None:
        metadata = DocumentMetadata()
    doc = DocxDocument(io.BytesIO(data))

    sections: list[Section] = []
    current_heading = ""
    current_level = 1
    current_content: list[ContentBlock] = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            if current_content:
                current_content.append(ContentBlock(text=""))
            continue

        is_heading = _is_heading_style(para)
        if is_heading:
            if current_heading or current_content:
                sections.append(Section(
                    section_type="",
                    heading=current_heading,
                    heading_level=current_level,
                    content=current_content,
                ))
            current_heading = text
            current_level = _get_heading_level(para)
            current_content = []
        else:
            block = _para_to_content_block(para)
            current_content.append(block)

    if current_heading or current_content:
        sections.append(Section(
            section_type="",
            heading=current_heading,
            heading_level=current_level,
            content=current_content,
        ))

    return DocumentModel(metadata=metadata, sections=sections)


def extract_format_profile(file_path: str | Path) -> FormatProfile:
    """Extract formatting profile from a DOCX for analysis."""
    doc = DocxDocument(str(file_path))
    fonts: dict[str, FontPattern] = {}
    headings: list[HeadingPattern] = []
    margins = None

    # Extract margins from first section
    if doc.sections:
        sec = doc.sections[0]
        margins = MarginPattern(
            top_inches=round(sec.top_margin.inches, 2) if sec.top_margin else 1.0,
            bottom_inches=round(sec.bottom_margin.inches, 2) if sec.bottom_margin else 1.0,
            left_inches=round(sec.left_margin.inches, 2) if sec.left_margin else 1.0,
            right_inches=round(sec.right_margin.inches, 2) if sec.right_margin else 1.0,
        )

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # Track fonts
        for run in para.runs:
            font_name = run.font.name or "Unknown"
            size = run.font.size
            size_pt = round(size.pt, 1) if size else 0
            key = f"{font_name}_{size_pt}"
            if key in fonts:
                fonts[key].frequency += 1
            else:
                fonts[key] = FontPattern(
                    font_name=font_name,
                    font_size_pt=size_pt,
                    bold=bool(run.font.bold),
                    italic=bool(run.font.italic),
                )

        # Track headings
        if _is_heading_style(para):
            alpha = "".join(c for c in text if c.isalpha())
            headings.append(HeadingPattern(
                text=text,
                level=_get_heading_level(para),
                bold=any(r.font.bold for r in para.runs if r.font.bold),
                centered=para.alignment == WD_ALIGN_PARAGRAPH.CENTER if para.alignment else False,
                all_caps=bool(alpha) and alpha == alpha.upper(),
            ))

    return FormatProfile(
        fonts=sorted(fonts.values(), key=lambda f: f.frequency, reverse=True),
        margins=margins,
        headings=headings,
        source_format="docx",
    )


def _is_heading_style(para) -> bool:
    """Check if a paragraph uses a heading style."""
    style_name = (para.style.name or "").lower()
    if "heading" in style_name:
        return True

    text = para.text.strip()
    if not text or len(text) > 120:
        return False

    # ALL CAPS with bold
    alpha = "".join(c for c in text if c.isalpha())
    has_bold = any(r.font.bold for r in para.runs if r.font.bold)
    is_caps = bool(alpha) and alpha == alpha.upper() and len(alpha) >= 3

    if is_caps and len(text.split()) <= 12:
        return True
    if has_bold and para.alignment == WD_ALIGN_PARAGRAPH.CENTER:
        return True

    return False


def _get_heading_level(para) -> int:
    """Determine heading level from style name or formatting."""
    style_name = (para.style.name or "").lower()
    if "heading 1" in style_name:
        return 1
    if "heading 2" in style_name:
        return 2
    if "heading 3" in style_name:
        return 3
    if "heading 4" in style_name:
        return 4

    text = para.text.strip()
    alpha = "".join(c for c in text if c.isalpha())
    if bool(alpha) and alpha == alpha.upper():
        return 1
    return 2


def _para_to_content_block(para) -> ContentBlock:
    """Convert a docx paragraph to a ContentBlock."""
    text = para.text.strip()
    has_bold = any(r.font.bold for r in para.runs if r.font.bold)
    has_italic = any(r.font.italic for r in para.runs if r.font.italic)
    is_centered = para.alignment == WD_ALIGN_PARAGRAPH.CENTER if para.alignment else False

    font_size = None
    for run in para.runs:
        if run.font.size:
            font_size = run.font.size.pt
            break

    return ContentBlock(
        text=text,
        bold=has_bold,
        italic=has_italic,
        centered=is_centered,
        font_size_pt=font_size,
        is_body_text=True,
    )
