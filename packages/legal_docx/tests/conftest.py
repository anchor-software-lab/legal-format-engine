"""Shared fixtures: synthesize a small but realistic brief.docx in a tmp dir.

Generating the fixture at test time (rather than checking in a .docx
binary) keeps the source tree text-only, makes the fixture's shape
auditable in code, and lets individual tests tweak the document
without committing new binary blobs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document as DocxDocument
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.shared import Inches, Pt


@pytest.fixture
def sample_brief_docx(tmp_path: Path) -> Path:
    """A 4-paragraph brief: title heading, body paragraph, block quote, conclusion.

    Deliberately introduces one rule-violating choice (12pt body font where
    the typical WI appellate rule expects 13pt) so the formatting checker
    can flag it in the end-to-end test.
    """
    doc = DocxDocument()

    section = doc.sections[0]
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)

    # 1) Heading
    heading = doc.add_heading("ARGUMENT I. STANDARD OF REVIEW", level=1)
    heading.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

    # 2) Body paragraph (intentionally 12pt to trigger a Finding)
    body = doc.add_paragraph()
    body.paragraph_format.first_line_indent = Inches(0.5)
    body.paragraph_format.line_spacing = 2.0
    run = body.add_run(
        "This Court reviews a circuit court's grant of summary judgment de "
        "novo, applying the same methodology as the circuit court."
    )
    run.font.name = "Times New Roman"
    run.font.size = Pt(12)

    # 3) Block quote (left-indented 0.5", no first-line indent)
    quote = doc.add_paragraph()
    quote.paragraph_format.left_indent = Inches(0.5)
    quote.paragraph_format.line_spacing = 1.0
    qrun = quote.add_run(
        "Summary judgment is appropriate if the pleadings, depositions, "
        "answers to interrogatories, and admissions on file, together with "
        "the affidavits, show that there is no genuine issue as to any "
        "material fact."
    )
    qrun.font.name = "Times New Roman"
    qrun.font.size = Pt(13)

    # 4) Conclusion paragraph (correct 13pt)
    concl = doc.add_paragraph()
    concl.paragraph_format.first_line_indent = Inches(0.5)
    concl.paragraph_format.line_spacing = 2.0
    crun = concl.add_run(
        "For the foregoing reasons, the order of the circuit court should "
        "be affirmed."
    )
    crun.font.name = "Times New Roman"
    crun.font.size = Pt(13)

    out = tmp_path / "sample_brief.docx"
    doc.save(out)
    return out
