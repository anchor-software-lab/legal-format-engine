"""Caption generation engine.

Generates jurisdiction-specific caption blocks from case metadata.
"""

from __future__ import annotations

from legal_format_engine.models.document import Alignment, CaptionBlock, ContentBlock
from legal_format_engine.models.metadata import DocumentMetadata, PartyRole
from legal_format_engine.rules.schema import CaptionRule


def _caption_line(text: str, bold: bool = False, italic: bool = False,
                  underline: bool = False, alignment: Alignment = Alignment.CENTER) -> ContentBlock:
    """Create a caption content block (single-spaced)."""
    return ContentBlock(
        text=text, bold=bold, italic=italic, underline=underline,
        alignment=alignment, is_caption=True,
    )


def _horizontal_rule(alignment: Alignment = Alignment.CENTER) -> ContentBlock:
    """Create a horizontal rule line for the caption page."""
    return ContentBlock(
        text="\u2500" * 50,  # box-drawing horizontal line
        alignment=alignment, is_caption=True,
    )


def generate_caption(metadata: DocumentMetadata, rule: CaptionRule) -> CaptionBlock:
    """Generate a formatted caption block from metadata and rules.

    Produces a Wisconsin-style appellate caption with:
    - Court name line (centered, all caps)
    - District line
    - Case number with horizontal rules
    - Party block with separator
    - Appeal-from line
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
    lines.append(_caption_line(
        text=court_name,
        bold=True,
        alignment=Alignment(rule.court_line_alignment),
    ))

    # District line (if applicable)
    if rule.include_district and metadata.case.district:
        lines.append(_caption_line(text=""))  # blank spacer
        lines.append(_caption_line(
            text=metadata.case.district.upper(),
            bold=True,
            alignment=Alignment(rule.court_line_alignment),
        ))

    # Blank spacer
    lines.append(_caption_line(text=""))

    # Case number
    prefix = rule.case_number_prefix or "Case No."
    lines.append(_caption_line(
        text=f"{prefix} {metadata.case.case_number}",
        bold=True,
        alignment=Alignment(rule.case_number_alignment),
    ))

    # ── Horizontal rule before parties ──
    lines.append(_caption_line(text=""))
    lines.append(_horizontal_rule())

    # Party block
    _add_party_lines(lines, metadata, rule)

    # "v." separator and second party are added by _add_party_lines

    # ── Horizontal rule after parties ──
    lines.append(_caption_line(text=""))
    lines.append(_horizontal_rule())

    # Appeal from line (if applicable)
    if rule.include_appeal_from and metadata.case.county_of_origin:
        lines.append(_caption_line(text=""))
        appeal_parts = [f"On an Appeal from a Judgment of Conviction,"]
        appeal_loc = f"Entered in the {metadata.case.county_of_origin} Circuit Court"
        if metadata.case.judge_name:
            appeal_loc += f", the\nHonorable {metadata.case.judge_name}, Presiding"
        appeal_parts.append(appeal_loc)
        for part in appeal_parts:
            lines.append(_caption_line(
                text=part,
                italic=True,
                alignment=Alignment(rule.appeal_from_alignment),
            ))
        lines.append(_caption_line(text=""))
        lines.append(_horizontal_rule())

    # Document title
    lines.append(_caption_line(text=""))
    doc_title = metadata.document_title
    if rule.document_title_style == "upper":
        doc_title = doc_title.upper()
    # Split multi-word titles like "BRIEF OF DEFENDANT-APPELLANT" onto separate lines
    title_words = doc_title.split()
    if len(title_words) > 3:
        mid = len(title_words) // 2
        line1 = " ".join(title_words[:mid])
        line2 = " ".join(title_words[mid:])
        lines.append(_caption_line(text=line1, bold=True,
                                   alignment=Alignment(rule.document_title_alignment)))
        lines.append(_caption_line(text=line2, bold=True,
                                   alignment=Alignment(rule.document_title_alignment)))
    else:
        lines.append(_caption_line(
            text=doc_title, bold=True,
            alignment=Alignment(rule.document_title_alignment),
        ))

    # ── Horizontal rule after title ──
    lines.append(_caption_line(text=""))
    lines.append(_horizontal_rule())

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

    # First party (typically State/Plaintiff)
    first_party = parties[0]
    lines.append(_caption_line(text=""))
    name = first_party.name.upper() if rule.party_name_style == "upper" else first_party.name
    lines.append(_caption_line(
        text=name + ",",
        bold=True,
        alignment=party_align,
    ))

    role_text = _format_role_label(first_party.role)
    if rule.party_role_style == "title":
        role_text = role_text.title()
    # Indent role if configured
    if rule.party_role_indented:
        lines.append(_caption_line(
            text=role_text + ".",
            alignment=party_align,
            italic=True,
        ))
    else:
        lines.append(_caption_line(
            text=role_text + ".",
            alignment=party_align,
        ))

    # Separator
    lines.append(_caption_line(text=""))
    lines.append(_caption_line(
        text=rule.party_separator,
        alignment=party_align,
    ))
    lines.append(_caption_line(text=""))

    # Second party (typically Defendant)
    if len(parties) > 1:
        second_party = parties[1]
        name2 = second_party.name.upper() if rule.party_name_style == "upper" else second_party.name
        lines.append(_caption_line(
            text=name2 + ",",
            bold=True,
            alignment=party_align,
        ))
        role_text2 = _format_role_label(second_party.role)
        if rule.party_role_style == "title":
            role_text2 = role_text2.title()
        if rule.party_role_indented:
            lines.append(_caption_line(
                text=role_text2 + ".",
                alignment=party_align,
                italic=True,
            ))
        else:
            lines.append(_caption_line(
                text=role_text2 + ".",
                alignment=party_align,
            ))

    # Additional parties (rare but possible)
    for party in parties[2:]:
        lines.append(_caption_line(text=""))
        name_extra = party.name.upper() if rule.party_name_style == "upper" else party.name
        lines.append(_caption_line(
            text=name_extra + ",",
            bold=True,
            alignment=party_align,
        ))
        lines.append(_caption_line(
            text=_format_role_label(party.role) + ".",
            alignment=party_align,
        ))


def _format_role_label(role: PartyRole) -> str:
    """Format a party role enum into a display label.

    >>> _format_role_label(PartyRole.DEFENDANT_APPELLANT)
    'Defendant-Appellant'
    """
    return role.value.replace("-", "-").title()
