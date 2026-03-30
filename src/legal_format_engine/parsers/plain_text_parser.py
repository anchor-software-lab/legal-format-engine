"""Plain text parser - converts raw text into structured document model."""

from __future__ import annotations
import re

from legal_format_engine.models.document import ContentBlock, DocumentModel, DocumentMetadata, Section


def parse_plain_text(
    text: str,
    metadata: DocumentMetadata | None = None,
) -> DocumentModel:
    """Parse plain text into a structured DocumentModel.

    Detects headings heuristically:
    - Lines in ALL CAPS (short enough to be headings)
    - Lines starting with numbering patterns (I., A., 1.)
    - Short bold-looking lines
    """
    if metadata is None:
        metadata = DocumentMetadata()

    lines = text.split("\n")
    sections: list[Section] = []
    current_heading = ""
    current_level = 1
    current_content: list[ContentBlock] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_content:
                current_content.append(ContentBlock(text=""))
            continue

        heading_info = _detect_heading(stripped)
        if heading_info:
            # Save previous section
            if current_heading or current_content:
                sections.append(Section(
                    section_type="",
                    heading=current_heading,
                    heading_level=current_level,
                    content=current_content,
                ))
            current_heading = heading_info["text"]
            current_level = heading_info["level"]
            current_content = []
        else:
            current_content.append(ContentBlock(text=stripped, is_body_text=True))

    # Save final section
    if current_heading or current_content:
        sections.append(Section(
            section_type="",
            heading=current_heading,
            heading_level=current_level,
            content=current_content,
        ))

    return DocumentModel(
        metadata=metadata,
        sections=sections,
    )


def _detect_heading(line: str) -> dict | None:
    """Detect if a line is likely a heading. Returns heading info or None."""
    # Too long to be a heading
    if len(line) > 120:
        return None

    # ALL CAPS line (and not just a short abbreviation)
    alpha = "".join(c for c in line if c.isalpha())
    if (
        len(alpha) >= 3
        and alpha == alpha.upper()
        and len(line.split()) <= 12
        and not line.endswith(".")
    ):
        return {"text": line, "level": 1}

    # Roman numeral prefix
    m = re.match(r"^([IVXLCDM]+)\.\s+(.+)", line)
    if m and len(m.group(1)) <= 6:
        return {"text": line, "level": 2}

    # Capital letter prefix
    m = re.match(r"^([A-Z])\.\s+(.+)", line)
    if m and len(line.split()) <= 15:
        return {"text": line, "level": 3}

    # Arabic numeral prefix
    m = re.match(r"^(\d+)\.\s+(.+)", line)
    if m and len(line.split()) <= 15:
        return {"text": line, "level": 4}

    return None
