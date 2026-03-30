"""Boilerplate engine - generates signature blocks and certifications."""

from __future__ import annotations
from typing import Optional

from legal_format_engine.models.document import Attorney, ContentBlock, Section
from legal_format_engine.models.section import CertificationTemplate, Ruleset


def generate_signature_block(
    attorney: Attorney,
    date: Optional[str] = None,
) -> Section:
    """Generate a signature block section."""
    lines: list[ContentBlock] = []

    lines.append(ContentBlock(text="Respectfully submitted,", is_body_text=True))
    lines.append(ContentBlock(text=""))

    if date:
        lines.append(ContentBlock(text=f"Dated: {date}", is_body_text=True))
        lines.append(ContentBlock(text=""))

    lines.append(ContentBlock(
        text=f"Electronically signed by {attorney.name}",
        is_body_text=True,
    ))
    lines.append(ContentBlock(text=f"_________________________", is_body_text=True))
    lines.append(ContentBlock(text=attorney.name, bold=True, is_body_text=True))

    if attorney.bar_number:
        lines.append(ContentBlock(text=f"Bar No. {attorney.bar_number}", is_body_text=True))

    if attorney.firm:
        lines.append(ContentBlock(text=attorney.firm, is_body_text=True))

    if attorney.address:
        for line in attorney.address.split("\n"):
            lines.append(ContentBlock(text=line.strip(), is_body_text=True))

    if attorney.phone:
        lines.append(ContentBlock(text=f"Phone: {attorney.phone}", is_body_text=True))

    if attorney.email:
        lines.append(ContentBlock(text=f"Email: {attorney.email}", is_body_text=True))

    return Section(
        section_type="signature_block",
        heading="",
        heading_level=0,
        content=lines,
    )


def generate_certifications(
    ruleset: Ruleset,
    attorney: Attorney,
    word_count: Optional[int] = None,
) -> list[Section]:
    """Generate certification sections from ruleset templates."""
    certifications = []

    for template in ruleset.certification_templates:
        if not template.required:
            continue

        text = template.template
        if word_count is not None:
            text = text.replace("{word_count}", str(word_count))

        lines: list[ContentBlock] = []

        # Title if present
        if template.title:
            lines.append(ContentBlock(
                text=template.title.upper(),
                bold=True,
                centered=True,
                is_heading=True,
            ))

        lines.append(ContentBlock(text=text, is_body_text=True))
        lines.append(ContentBlock(text=""))

        # Signature line
        lines.append(ContentBlock(
            text=f"_________________________",
            is_body_text=True,
        ))
        lines.append(ContentBlock(text=attorney.name, is_body_text=True))

        section = Section(
            section_type=f"certification_{template.cert_type}",
            heading=template.title or "",
            heading_level=1 if template.title else 0,
            content=lines,
        )
        certifications.append(section)

    return certifications
