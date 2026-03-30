"""DOCX parser for legal documents.

Reads existing Word documents and converts them to the internal
LegalDocument representation. Uses paragraph styles and formatting
cues for more accurate heading detection than plain text parsing.
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

from legal_format_engine.models.document import (
    Alignment,
    ContentBlock,
    HeadingLevel,
    LegalDocument,
    Section,
)
from legal_format_engine.utils.numbering import strip_numbering_prefix


def parse_docx(path: str | Path) -> LegalDocument:
    """Parse a DOCX file into a LegalDocument.

    Uses paragraph styles, formatting, and alignment to detect
    headings more accurately than plain text heuristics.

    Args:
        path: Path to the DOCX file.

    Returns:
        A LegalDocument with sections populated.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"DOCX file not found: {path}")

    docx = DocxDocument(str(path))
    paragraphs = _extract_paragraphs(docx)
    sections = _build_sections(paragraphs)

    return LegalDocument(
        sections=sections,
        raw_text=_extract_full_text(docx),
    )


def extract_format_profile(path: str | Path) -> dict:
    """Extract formatting details from a DOCX file.

    Useful for deriving rules from reference briefs.

    Returns a dict with detected formatting properties:
    - margins, fonts, font sizes, line spacing
    - heading styles detected
    - section names found
    """
    path = Path(path)
    docx = DocxDocument(str(path))
    profile: dict = {}

    # Page layout
    section = docx.sections[0]
    profile["page"] = {
        "width_inches": round(section.page_width / 914400, 2),
        "height_inches": round(section.page_height / 914400, 2),
        "margin_top_inches": round(section.top_margin / 914400, 2),
        "margin_bottom_inches": round(section.bottom_margin / 914400, 2),
        "margin_left_inches": round(section.left_margin / 914400, 2),
        "margin_right_inches": round(section.right_margin / 914400, 2),
    }

    # Font analysis
    fonts: dict[str, int] = {}
    font_sizes: dict[float, int] = {}
    bold_headings: list[str] = []
    centered_headings: list[str] = []
    all_caps_lines: list[str] = []
    section_headings: list[dict] = []

    for para in docx.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # Collect font info from runs
        for run in para.runs:
            if run.font.name:
                fonts[run.font.name] = fonts.get(run.font.name, 0) + len(run.text)
            if run.font.size:
                size = run.font.size / 12700  # EMU to points
                font_sizes[size] = font_sizes.get(size, 0) + len(run.text)

        # Detect heading patterns
        is_bold = all(run.bold for run in para.runs if run.text.strip())
        is_centered = para.alignment == WD_ALIGN_PARAGRAPH.CENTER
        is_all_caps = text == text.upper() and any(c.isalpha() for c in text)
        is_short = len(text) < 100

        if is_short and is_all_caps:
            all_caps_lines.append(text)

        if is_short and (is_bold or is_centered or is_all_caps):
            heading_info = {
                "text": text,
                "bold": is_bold,
                "centered": is_centered,
                "all_caps": is_all_caps,
                "style": para.style.name if para.style else None,
            }
            # Try to detect level
            if is_all_caps and is_centered:
                heading_info["detected_level"] = 1
            elif is_all_caps and not is_centered:
                heading_info["detected_level"] = 1
            else:
                prefix, _ = strip_numbering_prefix(text)
                if prefix and re.match(r"^[IVXLC]+\.$", prefix):
                    heading_info["detected_level"] = 2
                elif prefix and re.match(r"^[A-Z]\.$", prefix):
                    heading_info["detected_level"] = 3
                elif prefix and re.match(r"^\d+\.$", prefix):
                    heading_info["detected_level"] = 4
                else:
                    heading_info["detected_level"] = 2

            section_headings.append(heading_info)

    # Determine dominant font
    profile["fonts"] = {
        "dominant": max(fonts, key=fonts.get) if fonts else "Unknown",
        "all": dict(sorted(fonts.items(), key=lambda x: -x[1])),
    }
    profile["font_sizes"] = {
        "dominant_pt": max(font_sizes, key=font_sizes.get) if font_sizes else 0,
        "all_pt": dict(sorted(font_sizes.items(), key=lambda x: -x[1])),
    }
    profile["headings"] = section_headings
    profile["all_caps_lines"] = all_caps_lines

    return profile


def _extract_paragraphs(docx: DocxDocument) -> list[dict]:
    """Extract paragraph data with formatting metadata."""
    paragraphs = []
    for para in docx.paragraphs:
        text = para.text.strip()

        # Determine formatting
        is_bold = bool(para.runs and all(run.bold for run in para.runs if run.text.strip()))
        is_italic = bool(para.runs and all(run.italic for run in para.runs if run.text.strip()))
        is_underline = bool(
            para.runs and all(run.underline for run in para.runs if run.text.strip())
        )

        alignment = Alignment.LEFT
        if para.alignment == WD_ALIGN_PARAGRAPH.CENTER:
            alignment = Alignment.CENTER
        elif para.alignment == WD_ALIGN_PARAGRAPH.RIGHT:
            alignment = Alignment.RIGHT
        elif para.alignment == WD_ALIGN_PARAGRAPH.JUSTIFY:
            alignment = Alignment.JUSTIFY

        # Detect heading level
        level = _detect_heading_level_docx(text, is_bold, alignment, para)

        paragraphs.append({
            "text": text,
            "bold": is_bold,
            "italic": is_italic,
            "underline": is_underline,
            "alignment": alignment,
            "level": level,
            "style_name": para.style.name if para.style else None,
        })

    return paragraphs


def _detect_heading_level_docx(
    text: str,
    is_bold: bool,
    alignment: Alignment,
    para,
) -> HeadingLevel | None:
    """Detect heading level using DOCX formatting cues.

    More accurate than plain text since we have style, bold, and alignment info.
    """
    if not text or len(text) > 150:
        return None

    # Check Word heading styles first
    style_name = para.style.name if para.style else ""
    if style_name.startswith("Heading"):
        try:
            level = int(style_name.replace("Heading", "").strip())
            if 1 <= level <= 4:
                return HeadingLevel(level)
        except ValueError:
            pass

    alpha_chars = [c for c in text if c.isalpha()]
    is_all_caps = bool(alpha_chars) and all(c.isupper() for c in alpha_chars)

    # Level 1: ALL CAPS, typically centered or bold
    if is_all_caps and len(text) < 80 and len(alpha_chars) >= 3:
        if not text.endswith(","):  # Skip party names
            return HeadingLevel.LEVEL_1

    # Check numbering prefix
    prefix, remaining = strip_numbering_prefix(text)
    if prefix and len(remaining) < 120:
        prefix_clean = prefix.rstrip(".")
        if re.match(r"^[IVXLC]+$", prefix_clean, re.IGNORECASE):
            return HeadingLevel.LEVEL_2
        elif re.match(r"^[A-Z]$", prefix_clean):
            return HeadingLevel.LEVEL_3
        elif re.match(r"^\d+$", prefix_clean):
            return HeadingLevel.LEVEL_4

    # Bold short text that isn't all caps -> likely Level 2
    if is_bold and len(text) < 80 and not is_all_caps:
        return HeadingLevel.LEVEL_2

    return None


def _build_sections(paragraphs: list[dict]) -> list[Section]:
    """Build sections from parsed paragraphs."""
    sections: list[Section] = []
    current_content: list[ContentBlock] = []
    current_heading: str | None = None
    current_level: HeadingLevel | None = None
    section_counter = 0

    for para in paragraphs:
        if para["level"] is not None and para["text"]:
            # Save previous section
            if current_heading is not None:
                sections.append(_make_section(
                    current_heading, current_level, current_content, section_counter
                ))
                section_counter += 1
            elif current_content and any(b.text.strip() for b in current_content):
                sections.append(Section(
                    id="preamble",
                    heading_text="",
                    heading_level=HeadingLevel.LEVEL_1,
                    content=_trim_content(current_content),
                ))
                section_counter += 1

            current_heading = para["text"]
            current_level = para["level"]
            current_content = []
        else:
            block = ContentBlock(
                text=para["text"],
                bold=para["bold"],
                italic=para["italic"],
                underline=para["underline"],
                alignment=para["alignment"],
                is_body_text=True,
            )
            current_content.append(block)

    # Last section
    if current_heading is not None:
        sections.append(_make_section(
            current_heading, current_level, current_content, section_counter
        ))
    elif current_content and any(b.text.strip() for b in current_content):
        sections.append(Section(
            id="preamble",
            heading_text="",
            heading_level=HeadingLevel.LEVEL_1,
            content=_trim_content(current_content),
        ))

    return sections


def _make_section(
    heading: str,
    level: HeadingLevel | None,
    content: list[ContentBlock],
    index: int,
) -> Section:
    """Create a Section from heading and content."""
    slug = re.sub(r"[^\w\s]", "", heading.lower())
    slug = re.sub(r"\s+", "_", slug.strip())
    if not slug:
        slug = f"section_{index}"

    return Section(
        id=slug,
        heading_text=heading,
        heading_level=level or HeadingLevel.LEVEL_1,
        content=_trim_content(content),
    )


def _trim_content(blocks: list[ContentBlock]) -> list[ContentBlock]:
    """Remove leading and trailing empty content blocks."""
    while blocks and not blocks[0].text.strip():
        blocks = blocks[1:]
    while blocks and not blocks[-1].text.strip():
        blocks = blocks[:-1]
    return blocks


def _extract_full_text(docx: DocxDocument) -> str:
    """Extract all text from a DOCX for raw_text storage."""
    return "\n".join(para.text for para in docx.paragraphs)
