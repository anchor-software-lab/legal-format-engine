"""Markdown renderer for legal documents.

Produces clean Markdown output for debugging and previewing.
"""

from __future__ import annotations

from legal_format_engine.models.document import LegalDocument, Section


def render_markdown(doc: LegalDocument) -> str:
    """Render a LegalDocument as Markdown text.

    Args:
        doc: The internal document representation.

    Returns:
        Markdown-formatted string.
    """
    parts: list[str] = []

    # Caption
    if doc.caption:
        for line in doc.caption.lines:
            if line.text:
                if line.bold:
                    parts.append(f"**{line.text}**")
                else:
                    parts.append(line.text)
            else:
                parts.append("")
        parts.append("")
        parts.append("---")
        parts.append("")

    # Sections
    for section in doc.sections:
        _render_section(parts, section, depth=0)

    # Signature block
    if doc.signature_block:
        parts.append("")
        parts.append("---")
        parts.append("")
        sig = doc.signature_block
        parts.append("Respectfully submitted,")
        parts.append("")
        parts.append(f"**{sig.attorney_name}**  ")
        parts.append(f"State Bar No. {sig.bar_number}  ")
        if sig.firm:
            parts.append(f"{sig.firm}  ")
        parts.append(f"{sig.address}  ")
        parts.append(f"Phone: {sig.phone}  ")
        parts.append(f"Email: {sig.email}")

    # Certifications
    for cert in doc.certifications:
        parts.append("")
        parts.append("---")
        parts.append("")
        _render_section(parts, cert, depth=0)

    return "\n".join(parts)


def _render_section(parts: list[str], section: Section, depth: int) -> None:
    """Render a single section and its subsections."""
    if section.heading_text:
        level = max(section.heading_level, depth + 1)
        prefix = "#" * min(level, 6)
        heading = section.heading_text
        if section.numbering_prefix:
            heading = f"{section.numbering_prefix} {heading}"
        parts.append(f"{prefix} {heading}")
        parts.append("")

    for block in section.content:
        if block.text:
            parts.append(block.text)
        else:
            parts.append("")
    parts.append("")

    for sub in section.subsections:
        _render_section(parts, sub, depth + 1)
