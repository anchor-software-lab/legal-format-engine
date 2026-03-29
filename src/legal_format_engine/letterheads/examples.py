"""Example letterheads for development and testing.

These are NOT shipped with the product. They exist only as references
for how to construct letterhead profiles programmatically.
"""

from __future__ import annotations

from legal_format_engine.models.letterhead import Letterhead, LetterheadLine


def anchor_filings_letterhead() -> Letterhead:
    """Anchor Filings letterhead — development reference only.

    This is Nick Smith's Anchor Filings branding. It serves as the
    reference implementation for how a letterhead profile looks when
    fully configured. Not included in production builds.
    """
    return Letterhead(
        id="dev_anchor_filings",
        name="Anchor Filings",
        lines=[
            LetterheadLine(
                text="ANCHOR FILINGS",
                bold=True,
                font_size_pt=16,
                alignment="center",
            ),
            LetterheadLine(
                text="Legal Document Services",
                italic=True,
                font_size_pt=10,
                alignment="center",
            ),
            LetterheadLine(
                text="",
                alignment="center",
            ),
            LetterheadLine(
                text="Nicholas G. Smith | State Bar No. 1089586",
                font_size_pt=9,
                alignment="center",
            ),
            LetterheadLine(
                text="Office of the State Public Defender",
                font_size_pt=9,
                alignment="center",
            ),
            LetterheadLine(
                text="Post Office Box 7862, Madison, WI 53707-7862",
                font_size_pt=9,
                alignment="center",
            ),
            LetterheadLine(
                text="(608) 261-5417 | smithn@opd.wi.gov",
                font_size_pt=9,
                alignment="center",
            ),
        ],
        separator_line=True,
        spacing_after_pt=14.0,
    )


def blank_letterhead() -> Letterhead:
    """A minimal blank letterhead template users can customize."""
    return Letterhead(
        id="template_blank",
        name="Blank Template",
        lines=[
            LetterheadLine(
                text="[FIRM NAME]",
                bold=True,
                font_size_pt=14,
                alignment="center",
            ),
            LetterheadLine(
                text="[Address Line 1]",
                font_size_pt=9,
                alignment="center",
            ),
            LetterheadLine(
                text="[City, State ZIP]",
                font_size_pt=9,
                alignment="center",
            ),
            LetterheadLine(
                text="[Phone] | [Email]",
                font_size_pt=9,
                alignment="center",
            ),
        ],
        separator_line=True,
        spacing_after_pt=12.0,
    )
