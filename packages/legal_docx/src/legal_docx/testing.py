"""Shared docx fixture builders for tests.

Importable from any package's conftest so we don't duplicate the same
40-line "synthesize a brief" code in every package. Generating the
fixture at test time (rather than checking in a .docx binary) keeps the
source tree text-only and makes the fixture's shape auditable.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document as DocxDocument
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.shared import Inches, Pt


def make_sample_brief(out_path: str | Path) -> Path:
    """Build a 4-paragraph brief and write it to `out_path`.

    Shape: heading, body paragraph (intentionally 12pt to trigger a
    finding when the rule expects 13pt), block quote, conclusion. The
    body paragraph contains real citations (Tews, Brown) so the citation
    checkers have something to chew on too.
    """
    out_path = Path(out_path)
    doc = DocxDocument()

    section = doc.sections[0]
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)

    heading = doc.add_heading("ARGUMENT I. STANDARD OF REVIEW", level=1)
    heading.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    body = doc.add_paragraph()
    body.paragraph_format.first_line_indent = Inches(0.5)
    body.paragraph_format.line_spacing = 2.0
    body_run = body.add_run(
        "This Court reviews a circuit court's grant of summary judgment de "
        "novo. See Tews v. NHI, LLC, 2010 WI 137, ¶ 4, 330 Wis. 2d 389. "
        "See also Brown v. Holiday, 2008 WI 49."
    )
    body_run.font.name = "Times New Roman"
    body_run.font.size = Pt(12)

    quote = doc.add_paragraph()
    quote.paragraph_format.left_indent = Inches(0.5)
    quote.paragraph_format.line_spacing = 1.0
    quote_run = quote.add_run(
        "Summary judgment is appropriate if the pleadings, depositions, "
        "answers to interrogatories, and admissions on file show that "
        "there is no genuine issue as to any material fact."
    )
    quote_run.font.name = "Times New Roman"
    quote_run.font.size = Pt(13)

    concl = doc.add_paragraph()
    concl.paragraph_format.first_line_indent = Inches(0.5)
    concl.paragraph_format.line_spacing = 2.0
    concl_run = concl.add_run(
        "For the foregoing reasons, the order of the circuit court should "
        "be affirmed."
    )
    concl_run.font.name = "Times New Roman"
    concl_run.font.size = Pt(13)

    doc.save(str(out_path))
    return out_path
