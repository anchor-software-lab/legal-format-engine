"""Boilerplate block generation engine.

Generates signature blocks, certifications, and other standard blocks.
"""

from __future__ import annotations

from datetime import date

from legal_format_engine.models.document import (
    Alignment,
    ContentBlock,
    HeadingLevel,
    Section,
    SignatureBlock,
)
from legal_format_engine.models.metadata import DocumentMetadata
from legal_format_engine.rules.schema import CertificationRule


def generate_signature_block(metadata: DocumentMetadata) -> SignatureBlock:
    """Generate a signature block from attorney metadata.

    Args:
        metadata: Document metadata containing attorney info.

    Returns:
        A populated SignatureBlock.
    """
    return SignatureBlock(
        attorney_name=metadata.attorney.name,
        bar_number=metadata.attorney.bar_number,
        firm=metadata.attorney.firm,
        address=metadata.attorney.address,
        phone=metadata.attorney.phone,
        email=metadata.attorney.email,
    )


def generate_certifications(
    metadata: DocumentMetadata,
    rules: list[CertificationRule],
    word_count: int | None = None,
    service_parties: str | None = None,
) -> list[Section]:
    """Generate certification sections from templates.

    Args:
        metadata: Document metadata for template substitution.
        rules: List of certification rules with templates.
        word_count: Optional word count for compliance certification.
        service_parties: Optional formatted list of served parties.

    Returns:
        List of generated Section objects for each certification.
    """
    sections: list[Section] = []
    filed = metadata.date_filed or date.today()

    template_vars = _build_template_vars(metadata, filed, word_count, service_parties)

    for rule in rules:
        text = _render_template(rule.template, template_vars)
        section = Section(
            id=rule.id,
            heading_text=(rule.title or rule.id.replace("_", " ")).upper(),
            heading_level=HeadingLevel.LEVEL_1,
            content=[ContentBlock(text=text, alignment=Alignment.JUSTIFY, is_body_text=True)],
            is_generated=True,
        )
        sections.append(section)

    return sections


def _build_template_vars(
    metadata: DocumentMetadata,
    filed: date,
    word_count: int | None,
    service_parties: str | None,
) -> dict[str, str]:
    """Build the template variable dictionary for certification rendering."""
    return {
        "attorney_name": metadata.attorney.name,
        "bar_number": metadata.attorney.bar_number,
        "firm": metadata.attorney.firm or "",
        "address": metadata.attorney.address,
        "phone": metadata.attorney.phone,
        "email": metadata.attorney.email,
        "date_filed": filed.strftime("%B %d, %Y"),
        "day": str(filed.day),
        "month": filed.strftime("%B"),
        "year": str(filed.year),
        "word_count": str(word_count) if word_count else "[WORD COUNT]",
        "service_parties": service_parties or "[SERVICE PARTIES]",
        "signature_line": "____________________________",
        "case_number": metadata.case.case_number,
    }


def _render_template(template: str, variables: dict[str, str]) -> str:
    """Render a template string by substituting variables.

    Uses Python str.format_map with a defaulting dict so missing
    keys produce placeholder text instead of errors.
    """
    return template.format_map(_DefaultDict(variables))


class _DefaultDict(dict):
    """Dict that returns bracketed key name for missing keys."""

    def __missing__(self, key: str) -> str:
        return f"[{key.upper()}]"
