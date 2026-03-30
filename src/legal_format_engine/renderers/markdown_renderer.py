"""Markdown renderer - outputs documents as Markdown for preview/debug."""

from __future__ import annotations

from legal_format_engine.models.document import DocumentModel, Section, ContentBlock
from legal_format_engine.models.caption import CaptionBlock


def render_markdown(doc: DocumentModel) -> str:
    """Render a DocumentModel as Markdown."""
    parts: list[str] = []

    # Caption
    if doc.caption:
        parts.append(_render_caption(doc.caption))
        parts.append("")

    # Sections
    for section in doc.sections:
        parts.append(_render_section(section))
        parts.append("")

    # Certifications
    for cert in doc.certifications:
        parts.append(_render_section(cert))
        parts.append("")

    # Signature block
    if doc.signature_block:
        parts.append(_render_section(doc.signature_block))

    return "\n".join(parts)


def _render_caption(caption: CaptionBlock) -> str:
    lines = []
    for block in caption.lines:
        if block.bold:
            lines.append(f"**{block.text}**")
        else:
            lines.append(block.text)
    return "\n".join(lines)


def _render_section(section: Section) -> str:
    parts = []

    if section.heading:
        level = min(section.heading_level, 4) if section.heading_level > 0 else 1
        prefix = "#" * level
        heading_text = section.heading
        if section.numbering_prefix:
            heading_text = f"{section.numbering_prefix} {heading_text}"
        parts.append(f"{prefix} {heading_text}")
        parts.append("")

    for block in section.content:
        if not block.text:
            parts.append("")
        elif block.bold:
            parts.append(f"**{block.text}**")
        elif block.italic:
            parts.append(f"*{block.text}*")
        else:
            parts.append(block.text)

    for sub in section.subsections:
        parts.append(_render_section(sub))

    return "\n".join(parts)
