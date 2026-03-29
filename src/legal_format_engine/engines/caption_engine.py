"""Caption generation engine.

Generates jurisdiction-specific caption blocks from case metadata.
"""

from __future__ import annotations

from legal_format_engine.models.document import Alignment, CaptionBlock, ContentBlock
from legal_format_engine.models.metadata import DocumentMetadata, PartyRole
from legal_format_engine.rules.schema import CaptionRule


def generate_caption(metadata: DocumentMetadata, rule: CaptionRule) -> CaptionBlock:
    """Generate a formatted caption block from metadata and rules.

    Produces a Wisconsin-style appellate caption with:
    - Court name line (centered, all caps)
    - Case number (right-aligned)
    - Party names with separator
    - Document title

    Args:
        metadata: Full document metadata including case info.
        rule: Caption formatting rules.

    Returns:
        A CaptionBlock containing formatted lines.
    """
    lines: list[ContentBlock] = []

    # Court name line
    court_name = metadata.case.court_name
    if rule.court_line_style == "upper":
        court_name = court_name.upper()
    lines.append(ContentBlock(
        text=court_name,
        bold=True,
        alignment=Alignment(rule.court_line_alignment),
    ))

    # District line (if applicable)
    if rule.include_district and metadata.case.district:
        lines.append(ContentBlock(
            text=metadata.case.district.upper(),
            bold=True,
            alignment=Alignment(rule.court_line_alignment),
        ))

    # Blank separator line
    lines.append(ContentBlock(text="", alignment=Alignment.CENTER))

    # Appeal from line (if applicable)
    if rule.include_appeal_from and metadata.case.county_of_origin:
        appeal_from = f"Appeal from the Circuit Court of {metadata.case.county_of_origin}"
        if metadata.case.circuit_court_case_number:
            appeal_from += f", Case No. {metadata.case.circuit_court_case_number}"
        if metadata.case.judge_name:
            appeal_from += f", the Honorable {metadata.case.judge_name}, presiding"
        lines.append(ContentBlock(
            text=appeal_from,
            alignment=Alignment.CENTER,
            italic=True,
        ))
        lines.append(ContentBlock(text="", alignment=Alignment.CENTER))

    # Case number
    lines.append(ContentBlock(
        text=f"Case No. {metadata.case.case_number}",
        bold=True,
        alignment=Alignment(rule.case_number_alignment),
    ))

    # Blank separator
    lines.append(ContentBlock(text="", alignment=Alignment.CENTER))

    # Party block
    _add_party_lines(lines, metadata, rule)

    # Blank separator
    lines.append(ContentBlock(text="", alignment=Alignment.CENTER))

    # Document title
    doc_title = metadata.document_title
    if rule.document_title_style == "upper":
        doc_title = doc_title.upper()
    lines.append(ContentBlock(
        text=doc_title,
        bold=True,
        underline=True,
        alignment=Alignment(rule.document_title_alignment),
    ))

    return CaptionBlock(lines=lines)


def _add_party_lines(
    lines: list[ContentBlock],
    metadata: DocumentMetadata,
    rule: CaptionRule,
) -> None:
    """Add party name lines with separator to the caption."""
    parties = metadata.case.parties
    if not parties:
        return

    party_align = Alignment(rule.party_alignment)

    # Separate parties into sides based on role
    # First party listed (typically State/Plaintiff)
    first_party = parties[0]
    lines.append(ContentBlock(
        text=first_party.name.upper() + ",",
        bold=True,
        alignment=party_align,
    ))
    lines.append(ContentBlock(
        text=_format_role_label(first_party.role),
        alignment=party_align,
    ))

    # Separator
    lines.append(ContentBlock(text="", alignment=party_align))
    lines.append(ContentBlock(
        text=rule.party_separator,
        alignment=party_align,
    ))
    lines.append(ContentBlock(text="", alignment=party_align))

    # Second party (typically Defendant)
    if len(parties) > 1:
        second_party = parties[1]
        lines.append(ContentBlock(
            text=second_party.name.upper() + ",",
            bold=True,
            alignment=party_align,
        ))
        lines.append(ContentBlock(
            text=_format_role_label(second_party.role),
            alignment=party_align,
        ))

    # Additional parties (rare but possible)
    for party in parties[2:]:
        lines.append(ContentBlock(text="", alignment=party_align))
        lines.append(ContentBlock(
            text=party.name.upper() + ",",
            bold=True,
            alignment=party_align,
        ))
        lines.append(ContentBlock(
            text=_format_role_label(party.role),
            alignment=party_align,
        ))


def _format_role_label(role: PartyRole) -> str:
    """Format a party role enum into a display label.

    >>> _format_role_label(PartyRole.DEFENDANT_APPELLANT)
    'Defendant-Appellant'
    """
    return role.value.replace("-", "-").title()
