"""DOCX connector: extract formatting profile from DOCX files.

Uses python-docx to analyze paragraph styles, fonts, margins, headings,
and section structure from Word documents.
"""

from __future__ import annotations

from pathlib import Path

from anchor_ml_engine.models import NormalizedDocument
from anchor_ml_engine.normalizer import build_normalized_document


def extract_from_docx(
    path: str | Path,
    category: str | None = None,
    subcategory: str | None = None,
    document_type: str | None = None,
    author: str | None = None,
    organization: str | None = None,
) -> NormalizedDocument:
    """Analyze a DOCX file and return a NormalizedDocument.

    Extracts fonts, margins, heading styles, section structure,
    indentation, and other formatting patterns.

    Requires python-docx (pip install python-docx).
    """
    from docx import Document as DocxDocument
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    try:
        docx = DocxDocument(str(path))
    except Exception as exc:
        raise ValueError(f"Could not open DOCX file: {exc}") from exc

    # -- Page layout / margins --
    margins = None
    if docx.sections:
        sec = docx.sections[0]
        margins = {
            "top": round(sec.top_margin / 914400, 2),
            "bottom": round(sec.bottom_margin / 914400, 2),
            "left": round(sec.left_margin / 914400, 2),
            "right": round(sec.right_margin / 914400, 2),
        }

    # -- Font analysis (sample body paragraphs) --
    font_counts: dict[str, int] = {}
    size_counts: dict[float, int] = {}
    line_spacings: list[float] = []
    indent_values: list[float] = []
    block_quote_indents: list[float] = []
    heading_infos: list[dict] = []

    for para in docx.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # Collect font info from runs
        for run in para.runs:
            run_text = run.text.strip()
            if not run_text:
                continue
            if run.font.name:
                font_counts[run.font.name] = (
                    font_counts.get(run.font.name, 0) + len(run_text)
                )
            if run.font.size:
                size_pt = round(run.font.size / 12700, 1)
                size_counts[size_pt] = size_counts.get(size_pt, 0) + len(run_text)

        # Line spacing
        pf = para.paragraph_format
        if pf.line_spacing is not None:
            try:
                spacing_val = float(pf.line_spacing)
                if spacing_val < 10:
                    line_spacings.append(spacing_val)
                else:
                    line_spacings.append(round(spacing_val / 914400 * 72 / 12, 1))
            except (TypeError, ValueError):
                pass

        # Indentation
        is_body = len(text) > 100
        if is_body and pf.first_line_indent is not None:
            try:
                indent_in = round(pf.first_line_indent / 914400, 2)
                if 0 < indent_in < 2:
                    indent_values.append(indent_in)
            except (TypeError, ValueError):
                pass

        # Block quote detection
        if pf.left_indent is not None:
            try:
                left_in = round(pf.left_indent / 914400, 2)
                if 0.3 < left_in < 3.0 and 30 < len(text) < 500:
                    block_quote_indents.append(left_in)
            except (TypeError, ValueError):
                pass

        # Heading detection
        is_bold = bool(para.runs and all(
            run.bold for run in para.runs if run.text.strip()
        ))
        is_centered = para.alignment == WD_ALIGN_PARAGRAPH.CENTER
        alpha_chars = [c for c in text if c.isalpha()]
        is_all_caps = bool(alpha_chars) and all(c.isupper() for c in alpha_chars)
        is_short = len(text) < 120

        if is_short and (is_bold or is_centered or is_all_caps):
            h_size = None
            for run in para.runs:
                if run.font.size and run.text.strip():
                    h_size = round(run.font.size / 12700, 1)
                    break

            heading_infos.append({
                "text": text,
                "bold": is_bold,
                "centered": is_centered,
                "all_caps": is_all_caps,
                "font_size": h_size,
            })

    # -- Build font list --
    fonts = []
    if font_counts:
        dominant_font = max(font_counts, key=font_counts.get)
        dominant_size = max(size_counts, key=size_counts.get) if size_counts else 12.0
        fonts.append({"font_name": dominant_font, "font_size_pt": dominant_size})

    # -- Line spacing --
    avg_spacing = None
    if line_spacings:
        avg_spacing = round(sum(line_spacings) / len(line_spacings), 1)

    # -- Paragraph indent --
    avg_indent = None
    if indent_values:
        avg_indent = round(sum(indent_values) / len(indent_values), 2)

    # -- Block quote indent --
    avg_bq_indent = None
    if block_quote_indents:
        avg_bq_indent = round(sum(block_quote_indents) / len(block_quote_indents), 2)

    return build_normalized_document(
        source_filename=path.name,
        source_format="docx",
        fonts=fonts or None,
        margins=margins,
        line_spacing=avg_spacing,
        body_indent=avg_indent,
        block_quote_indent=avg_bq_indent,
        category=category,
        subcategory=subcategory,
        document_type=document_type,
        author=author,
        organization=organization,
    )
