"""Caption engine - generates formatted caption blocks from case metadata."""

from __future__ import annotations
from typing import Optional

from legal_format_engine.models.document import CaseMetadata, ContentBlock
from legal_format_engine.models.caption import CaptionBlock
from legal_format_engine.models.section import Ruleset


DISTRICT_MAP = {
    "1": "District I",
    "2": "District II",
    "3": "District III",
    "4": "District IV",
}


def generate_caption(
    case_meta: CaseMetadata,
    doc_title: str,
    ruleset: Optional[Ruleset] = None,
) -> CaptionBlock:
    """Generate a full caption block from case metadata.

    Returns a CaptionBlock with court name, parties, case number, and document title.
    """
    lines: list[ContentBlock] = []

    # Court name
    court_name = case_meta.court_name or _default_court_name(ruleset)
    lines.append(ContentBlock(
        text=court_name.upper(),
        bold=True,
        centered=True,
        is_caption=True,
    ))

    # Horizontal rule
    lines.append(ContentBlock(
        text="─" * 50,
        centered=True,
        is_caption=True,
    ))

    # District if applicable
    if case_meta.district:
        district_text = DISTRICT_MAP.get(case_meta.district, case_meta.district)
        lines.append(ContentBlock(
            text=district_text,
            centered=True,
            is_caption=True,
        ))

    # Parties
    party_lines = _format_parties(case_meta)
    lines.extend(party_lines)

    # Horizontal rule
    lines.append(ContentBlock(
        text="─" * 50,
        centered=True,
        is_caption=True,
    ))

    # Case number
    if case_meta.case_number:
        lines.append(ContentBlock(
            text=f"Case No. {case_meta.case_number}",
            centered=True,
            bold=True,
            is_caption=True,
        ))

    # Horizontal rule
    lines.append(ContentBlock(
        text="─" * 50,
        centered=True,
        is_caption=True,
    ))

    # Document title
    if doc_title:
        lines.append(ContentBlock(
            text=doc_title.upper(),
            bold=True,
            centered=True,
            is_caption=True,
        ))

    caption = CaptionBlock(
        court_name=court_name,
        district=case_meta.district,
        case_number=case_meta.case_number,
        document_title=doc_title,
        lines=lines,
    )

    return caption


def _default_court_name(ruleset: Optional[Ruleset]) -> str:
    if ruleset and ruleset.jurisdiction == "wisconsin":
        if ruleset.court_level == "court_of_appeals":
            return "STATE OF WISCONSIN COURT OF APPEALS"
        elif ruleset.court_level == "supreme_court":
            return "SUPREME COURT OF WISCONSIN"
        elif ruleset.court_level == "circuit_court":
            return "CIRCUIT COURT OF WISCONSIN"
    return "COURT"


def _format_parties(case_meta: CaseMetadata) -> list[ContentBlock]:
    """Format party names with roles and v. separator."""
    lines = []
    parties = case_meta.parties

    if not parties:
        return lines

    for i, party in enumerate(parties):
        designation = party.designation or f"{party.role.value.title()}"
        name_line = party.name.upper() + ","
        lines.append(ContentBlock(
            text=name_line,
            is_caption=True,
        ))
        lines.append(ContentBlock(
            text=f"        {designation},",
            is_caption=True,
        ))

        if i < len(parties) - 1:
            lines.append(ContentBlock(
                text="    v.",
                is_caption=True,
            ))

    return lines
