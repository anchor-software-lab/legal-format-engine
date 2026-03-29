"""PDF parser for legal documents.

Extracts text and structure from PDF files using PyMuPDF (fitz).
Detects headings based on font size, weight, and positioning.
"""

from __future__ import annotations

import re
from pathlib import Path

import fitz  # PyMuPDF

from legal_format_engine.models.document import (
    Alignment,
    ContentBlock,
    HeadingLevel,
    LegalDocument,
    Section,
)
from legal_format_engine.utils.numbering import strip_numbering_prefix


def parse_pdf(path: str | Path) -> LegalDocument:
    """Parse a PDF file into a LegalDocument.

    Uses font metrics and positioning to detect headings and
    section structure.

    Args:
        path: Path to the PDF file.

    Returns:
        A LegalDocument with sections populated.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    doc = fitz.open(str(path))
    blocks = _extract_blocks(doc)
    paragraphs = _merge_into_paragraphs(blocks)
    sections = _build_sections(paragraphs)

    raw_text = "\n".join(p["text"] for p in paragraphs)

    doc.close()

    return LegalDocument(
        sections=sections,
        raw_text=raw_text,
    )


def extract_pdf_format_profile(path: str | Path) -> dict:
    """Extract formatting details from a PDF file.

    Returns a dict with detected formatting properties:
    - page dimensions, margins (estimated)
    - font names and sizes used
    - heading candidates
    """
    path = Path(path)
    doc = fitz.open(str(path))
    profile: dict = {}

    # Page dimensions from first page
    page = doc[0]
    rect = page.rect
    profile["page"] = {
        "width_inches": round(rect.width / 72, 2),
        "height_inches": round(rect.height / 72, 2),
    }

    # Analyze all text spans for font info
    fonts: dict[str, int] = {}
    font_sizes: dict[float, int] = {}
    all_caps_lines: list[str] = []
    heading_candidates: list[dict] = []

    # Estimate margins from text bounding boxes
    min_x = float("inf")
    max_x = 0.0
    min_y = float("inf")
    max_y = 0.0

    for page in doc:
        text_dict = page.get_text("dict")
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # text blocks only
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue

                    font_name = span.get("font", "Unknown")
                    font_size = round(span.get("size", 0), 1)
                    flags = span.get("flags", 0)
                    is_bold = bool(flags & 2**4)  # bit 4 = bold

                    fonts[font_name] = fonts.get(font_name, 0) + len(text)
                    font_sizes[font_size] = font_sizes.get(font_size, 0) + len(text)

                    # Track text boundaries for margin estimation
                    bbox = span.get("bbox", (0, 0, 0, 0))
                    if len(text) > 5:  # skip tiny fragments
                        min_x = min(min_x, bbox[0])
                        max_x = max(max_x, bbox[2])
                        min_y = min(min_y, bbox[1])
                        max_y = max(max_y, bbox[3])

        # Collect full lines for heading detection
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                line_text = "".join(
                    span.get("text", "") for span in line.get("spans", [])
                ).strip()
                if not line_text or len(line_text) > 150:
                    continue

                spans = line.get("spans", [])
                if not spans:
                    continue

                first_span = spans[0]
                font_size = round(first_span.get("size", 0), 1)
                flags = first_span.get("flags", 0)
                is_bold = bool(flags & 2**4)
                bbox = line.get("bbox", (0, 0, 0, 0))

                # Check centering (rough heuristic)
                line_center = (bbox[0] + bbox[2]) / 2
                page_center = rect.width / 2
                is_centered = abs(line_center - page_center) < 36  # ~0.5 inch tolerance

                alpha_chars = [c for c in line_text if c.isalpha()]
                is_all_caps = bool(alpha_chars) and all(c.isupper() for c in alpha_chars)

                if is_all_caps and len(line_text) < 100:
                    all_caps_lines.append(line_text)

                if is_bold or is_centered or is_all_caps:
                    heading_candidates.append({
                        "text": line_text,
                        "bold": is_bold,
                        "centered": is_centered,
                        "all_caps": is_all_caps,
                        "font_size": font_size,
                        "font": first_span.get("font", ""),
                    })

    # Estimate margins
    if min_x < float("inf"):
        profile["margins_estimated"] = {
            "left_inches": round(min_x / 72, 2),
            "right_inches": round((rect.width - max_x) / 72, 2),
            "top_inches": round(min_y / 72, 2),
            "bottom_inches": round((rect.height - max_y) / 72, 2),
        }

    profile["fonts"] = {
        "dominant": max(fonts, key=fonts.get) if fonts else "Unknown",
        "all": dict(sorted(fonts.items(), key=lambda x: -x[1])),
    }
    profile["font_sizes"] = {
        "dominant_pt": max(font_sizes, key=font_sizes.get) if font_sizes else 0,
        "all_pt": dict(sorted(font_sizes.items(), key=lambda x: -x[1])),
    }
    profile["headings"] = heading_candidates
    profile["all_caps_lines"] = all_caps_lines

    doc.close()
    return profile


def _extract_blocks(doc: fitz.Document) -> list[dict]:
    """Extract text blocks with formatting metadata from all pages."""
    blocks = []

    for page in doc:
        text_dict = page.get_text("dict")
        page_width = page.rect.width

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue

            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue

                line_text = "".join(span.get("text", "") for span in spans).strip()
                if not line_text:
                    continue

                # Use first span for formatting info
                first_span = spans[0]
                font_size = round(first_span.get("size", 0), 1)
                flags = first_span.get("flags", 0)
                is_bold = bool(flags & 2**4)
                is_italic = bool(flags & 2**1)

                bbox = line.get("bbox", (0, 0, 0, 0))
                line_center = (bbox[0] + bbox[2]) / 2
                page_center = page_width / 2
                is_centered = abs(line_center - page_center) < 36

                blocks.append({
                    "text": line_text,
                    "font_size": font_size,
                    "bold": is_bold,
                    "italic": is_italic,
                    "centered": is_centered,
                    "bbox": bbox,
                    "font": first_span.get("font", ""),
                })

    return blocks


def _merge_into_paragraphs(blocks: list[dict]) -> list[dict]:
    """Merge consecutive lines into paragraphs.

    Lines with the same formatting that are close together vertically
    get merged. Lines that look like headings stay separate.
    """
    if not blocks:
        return []

    paragraphs: list[dict] = []
    current: dict | None = None

    for block in blocks:
        is_heading = _is_heading_block(block)

        if current is None:
            current = dict(block)
            current["is_heading"] = is_heading
            continue

        # Start a new paragraph if formatting changes or it's a heading
        same_format = (
            block["bold"] == current["bold"]
            and block["centered"] == current["centered"]
            and abs(block["font_size"] - current["font_size"]) < 0.5
        )

        if is_heading or current["is_heading"] or not same_format:
            paragraphs.append(current)
            current = dict(block)
            current["is_heading"] = is_heading
        else:
            # Merge into current paragraph
            current["text"] = current["text"] + " " + block["text"]
            current["bbox"] = (
                min(current["bbox"][0], block["bbox"][0]),
                min(current["bbox"][1], block["bbox"][1]),
                max(current["bbox"][2], block["bbox"][2]),
                max(current["bbox"][3], block["bbox"][3]),
            )

    if current:
        paragraphs.append(current)

    return paragraphs


def _is_heading_block(block: dict) -> bool:
    """Determine if a block looks like a heading."""
    text = block["text"]
    if not text or len(text) > 150:
        return False

    alpha = [c for c in text if c.isalpha()]
    is_all_caps = bool(alpha) and all(c.isupper() for c in alpha) and len(alpha) >= 3

    if is_all_caps and len(text) < 100:
        return True
    if block["bold"] and len(text) < 100:
        return True
    if block["centered"] and len(text) < 80:
        return True

    # Check for numbering prefix
    prefix, _ = strip_numbering_prefix(text)
    if prefix and len(text) < 120:
        return True

    return False


def _detect_heading_level(block: dict) -> HeadingLevel | None:
    """Detect heading level from PDF block formatting."""
    text = block["text"]
    if not text or len(text) > 150:
        return None

    alpha = [c for c in text if c.isalpha()]
    is_all_caps = bool(alpha) and all(c.isupper() for c in alpha)

    # Level 1: ALL CAPS (centered or not)
    if is_all_caps and len(text) < 100 and len(alpha) >= 3:
        if not text.endswith(","):  # Skip party names in caption
            return HeadingLevel.LEVEL_1

    # Check numbering prefix for sub-levels
    prefix, remaining = strip_numbering_prefix(text)
    if prefix and len(remaining) < 120:
        prefix_clean = prefix.rstrip(".")
        if re.match(r"^[IVXLC]+$", prefix_clean, re.IGNORECASE):
            return HeadingLevel.LEVEL_2
        elif re.match(r"^[A-Z]$", prefix_clean):
            return HeadingLevel.LEVEL_3
        elif re.match(r"^\d+$", prefix_clean):
            return HeadingLevel.LEVEL_4

    # Bold short text -> Level 2
    if block["bold"] and len(text) < 100 and not is_all_caps:
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
        level = _detect_heading_level(para) if para.get("is_heading") else None

        alignment = Alignment.CENTER if para.get("centered") else Alignment.LEFT

        if level is not None and para["text"]:
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
            current_level = level
            current_content = []
        else:
            block = ContentBlock(
                text=para["text"],
                bold=para.get("bold", False),
                italic=para.get("italic", False),
                alignment=alignment,
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
