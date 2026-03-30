"""Plain text parser for legal documents.

Converts unstructured text into a LegalDocument by detecting
headings, sections, and content blocks heuristically.
"""

from __future__ import annotations

import re

from legal_format_engine.models.document import (
    ContentBlock,
    HeadingLevel,
    LegalDocument,
    Section,
)
from legal_format_engine.utils.numbering import NUMBERING_PREFIX_PATTERN, strip_numbering_prefix
from legal_format_engine.utils.text import normalize_whitespace, strip_unicode_control


def parse_plain_text(text: str) -> LegalDocument:
    """Parse plain text into a LegalDocument with best-effort section detection.

    The parser identifies headings heuristically and groups content
    into sections. It does NOT extract metadata - that must be
    provided separately.

    Args:
        text: Raw document text.

    Returns:
        A LegalDocument with sections populated from detected headings.
    """
    text = strip_unicode_control(text)
    lines = text.split("\n")
    classified = _classify_lines(lines)
    sections = _build_sections(classified)

    return LegalDocument(
        sections=sections,
        raw_text=text,
    )


def _classify_lines(lines: list[str]) -> list[tuple[str, str, HeadingLevel | None]]:
    """Classify each line as a heading or content.

    Returns a list of (type, text, level) tuples where type is
    "heading" or "content".
    """
    result: list[tuple[str, str, HeadingLevel | None]] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            # Preserve blank lines as empty content
            result.append(("content", "", None))
            continue

        level = _detect_heading_level(stripped)
        if level is not None:
            result.append(("heading", stripped, level))
        else:
            result.append(("content", stripped, None))

    return result


def _detect_heading_level(line: str) -> HeadingLevel | None:
    """Detect whether a line is a heading and what level.

    Heuristics:
    - ALL CAPS, short, no ending punctuation except period -> Level 1
    - Starts with Roman numeral prefix -> Level 2
    - Starts with capital letter prefix (A., B.) -> Level 3
    - Starts with arabic number prefix (1., 2.) -> Level 4
    """
    # Too long for a heading
    if len(line) > 150:
        return None

    # Check for numbering prefix first (more specific)
    prefix, remaining = strip_numbering_prefix(line)

    if prefix:
        # Determine level from prefix type
        prefix_clean = prefix.rstrip(".")
        if re.match(r"^[IVXLC]+$", prefix_clean, re.IGNORECASE):
            # Roman numeral -> Level 2
            if len(remaining) < 120:
                return HeadingLevel.LEVEL_2
        elif re.match(r"^[A-Z]$", prefix_clean):
            # Single capital letter -> Level 3
            if len(remaining) < 120:
                return HeadingLevel.LEVEL_3
        elif re.match(r"^\d+$", prefix_clean):
            # Arabic number -> Level 4
            if len(remaining) < 120:
                return HeadingLevel.LEVEL_4

    # ALL CAPS check for Level 1
    # Must be reasonably short, mostly letters, and all uppercase
    alpha_chars = [c for c in line if c.isalpha()]
    if (
        alpha_chars
        and all(c.isupper() for c in alpha_chars)
        and len(line) < 80
        and not line.endswith(",")  # Avoid party names in captions
        and len(alpha_chars) >= 3  # At least 3 letters
    ):
        return HeadingLevel.LEVEL_1

    return None


def _build_sections(
    classified: list[tuple[str, str, HeadingLevel | None]],
) -> list[Section]:
    """Build a flat list of sections from classified lines.

    Groups content lines under the preceding heading. Content
    before any heading goes into a preamble section.
    """
    sections: list[Section] = []
    current_content: list[ContentBlock] = []
    current_heading: str | None = None
    current_level: HeadingLevel | None = None
    section_counter = 0

    for line_type, text, level in classified:
        if line_type == "heading":
            # Save previous section if there was a heading
            if current_heading is not None:
                sections.append(_make_section(
                    current_heading, current_level, current_content, section_counter
                ))
                section_counter += 1
            elif current_content and any(block.text.strip() for block in current_content):
                # Content before first heading -> preamble
                sections.append(Section(
                    id="preamble",
                    heading_text="",
                    heading_level=HeadingLevel.LEVEL_1,
                    content=_trim_content(current_content),
                ))
                section_counter += 1

            current_heading = text
            current_level = level
            current_content = []
        else:
            current_content.append(ContentBlock(text=text, is_body_text=True))

    # Don't forget the last section
    if current_heading is not None:
        sections.append(_make_section(
            current_heading, current_level, current_content, section_counter
        ))
    elif current_content and any(block.text.strip() for block in current_content):
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
    """Create a Section from parsed heading and content."""
    # Generate a slug id from the heading
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
    # Strip leading empties
    while blocks and not blocks[0].text.strip():
        blocks = blocks[1:]
    # Strip trailing empties
    while blocks and not blocks[-1].text.strip():
        blocks = blocks[:-1]
    return blocks
