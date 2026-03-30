"""PDF parser - reads PDF documents into structured document model."""

from __future__ import annotations
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from legal_format_engine.models.document import ContentBlock, DocumentModel, DocumentMetadata, Section
from legal_format_engine.models.patterns import FormatProfile, FontPattern, MarginPattern, HeadingPattern


def parse_pdf(
    file_path: str | Path,
    metadata: Optional[DocumentMetadata] = None,
) -> DocumentModel:
    """Parse a PDF file into a structured DocumentModel."""
    if metadata is None:
        metadata = DocumentMetadata()

    doc = fitz.open(str(file_path))
    sections: list[Section] = []
    current_heading = ""
    current_level = 1
    current_content: list[ContentBlock] = []

    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block["type"] != 0:  # text block
                continue
            for line_data in block.get("lines", []):
                spans = line_data.get("spans", [])
                if not spans:
                    continue

                text = "".join(s["text"] for s in spans).strip()
                if not text:
                    continue

                # Detect heading from font properties
                max_size = max(s["size"] for s in spans)
                is_bold = any("bold" in s.get("font", "").lower() for s in spans)

                heading_info = _detect_pdf_heading(text, max_size, is_bold)
                if heading_info:
                    if current_heading or current_content:
                        sections.append(Section(
                            section_type="",
                            heading=current_heading,
                            heading_level=current_level,
                            content=current_content,
                        ))
                    current_heading = text
                    current_level = heading_info["level"]
                    current_content = []
                else:
                    current_content.append(ContentBlock(
                        text=text,
                        font_size_pt=max_size,
                        bold=is_bold,
                        is_body_text=True,
                    ))

    doc.close()

    if current_heading or current_content:
        sections.append(Section(
            section_type="",
            heading=current_heading,
            heading_level=current_level,
            content=current_content,
        ))

    return DocumentModel(metadata=metadata, sections=sections)


def parse_pdf_bytes(
    data: bytes,
    metadata: Optional[DocumentMetadata] = None,
) -> DocumentModel:
    """Parse PDF from bytes."""
    if metadata is None:
        metadata = DocumentMetadata()

    doc = fitz.open(stream=data, filetype="pdf")
    sections: list[Section] = []
    current_heading = ""
    current_level = 1
    current_content: list[ContentBlock] = []

    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block["type"] != 0:
                continue
            for line_data in block.get("lines", []):
                spans = line_data.get("spans", [])
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans).strip()
                if not text:
                    continue
                max_size = max(s["size"] for s in spans)
                is_bold = any("bold" in s.get("font", "").lower() for s in spans)

                heading_info = _detect_pdf_heading(text, max_size, is_bold)
                if heading_info:
                    if current_heading or current_content:
                        sections.append(Section(
                            section_type="",
                            heading=current_heading,
                            heading_level=current_level,
                            content=current_content,
                        ))
                    current_heading = text
                    current_level = heading_info["level"]
                    current_content = []
                else:
                    current_content.append(ContentBlock(
                        text=text,
                        font_size_pt=max_size,
                        bold=is_bold,
                        is_body_text=True,
                    ))

    doc.close()

    if current_heading or current_content:
        sections.append(Section(
            section_type="",
            heading=current_heading,
            heading_level=current_level,
            content=current_content,
        ))

    return DocumentModel(metadata=metadata, sections=sections)


def extract_format_profile(file_path: str | Path) -> FormatProfile:
    """Extract formatting profile from a PDF for analysis."""
    doc = fitz.open(str(file_path))
    fonts: dict[str, FontPattern] = {}
    headings: list[HeadingPattern] = []

    # Estimate margins from first page
    margins = None
    if len(doc) > 0:
        page = doc[0]
        width = page.rect.width / 72.0  # points to inches
        height = page.rect.height / 72.0
        blocks = page.get_text("dict")["blocks"]
        if blocks:
            text_blocks = [b for b in blocks if b["type"] == 0]
            if text_blocks:
                min_x = min(b["bbox"][0] for b in text_blocks) / 72.0
                min_y = min(b["bbox"][1] for b in text_blocks) / 72.0
                max_x = max(b["bbox"][2] for b in text_blocks) / 72.0
                max_y = max(b["bbox"][3] for b in text_blocks) / 72.0
                margins = MarginPattern(
                    top_inches=round(min_y, 2),
                    bottom_inches=round(height - max_y, 2),
                    left_inches=round(min_x, 2),
                    right_inches=round(width - max_x, 2),
                    confidence=0.6,
                )

    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block["type"] != 0:
                continue
            for line_data in block.get("lines", []):
                for span in line_data.get("spans", []):
                    font_name = span.get("font", "Unknown")
                    size = round(span.get("size", 0), 1)
                    key = f"{font_name}_{size}"
                    if key in fonts:
                        fonts[key].frequency += 1
                    else:
                        fonts[key] = FontPattern(
                            font_name=font_name,
                            font_size_pt=size,
                            bold="bold" in font_name.lower(),
                            italic="italic" in font_name.lower(),
                        )

                text = "".join(s["text"] for s in line_data.get("spans", [])).strip()
                if text:
                    max_size = max(s["size"] for s in line_data["spans"])
                    is_bold = any("bold" in s.get("font", "").lower() for s in line_data["spans"])
                    heading_info = _detect_pdf_heading(text, max_size, is_bold)
                    if heading_info:
                        alpha = "".join(c for c in text if c.isalpha())
                        headings.append(HeadingPattern(
                            text=text,
                            level=heading_info["level"],
                            bold=is_bold,
                            all_caps=bool(alpha) and alpha == alpha.upper(),
                        ))

    doc.close()

    return FormatProfile(
        fonts=sorted(fonts.values(), key=lambda f: f.frequency, reverse=True),
        margins=margins,
        headings=headings,
        source_format="pdf",
        confidence=0.6,
    )


def _detect_pdf_heading(text: str, font_size: float, is_bold: bool) -> dict | None:
    """Detect if text is a heading based on font properties."""
    if len(text) > 120:
        return None
    if len(text.split()) > 12:
        return None

    alpha = "".join(c for c in text if c.isalpha())
    is_caps = bool(alpha) and alpha == alpha.upper() and len(alpha) >= 3

    if is_caps and is_bold and font_size >= 11:
        return {"level": 1}
    if is_caps and font_size >= 12:
        return {"level": 1}
    if is_bold and font_size >= 13:
        return {"level": 1}
    if is_bold and font_size >= 11:
        return {"level": 2}

    return None
