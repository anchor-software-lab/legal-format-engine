"""Apply suggestions back into a .docx.

v0 surface — REFORMAT suggestions only.

A REFORMAT suggestion carries a `new_style: ObservedStyle` describing
the corrected formatting for a Segment. We open the original docx,
locate the paragraph by ordinal, and apply the new style values to its
runs and paragraph-format properties.

The next iteration of v0 will add:
- REPLACE / INSERT / DELETE handling for citation auto-fixes.
- True Word "tracked changes" (`<w:ins>` / `<w:del>` wrappers) so the
  user can accept or reject each edit. For now we apply changes
  directly; the user can compare against the original to review.
- Word comments (`comments.xml`) anchored to finding ranges for
  non-auto-apply findings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from docx import Document as load_docx_document
from docx.shared import Inches, Pt

from legal_quality_gate.types import ObservedStyle, Suggestion, SuggestionKind


def write_annotated(
    *,
    original_path: str | Path,
    suggestions: Iterable[Suggestion],
    out_path: str | Path,
    segment_ordinal_by_id: dict[str, int],
) -> Path:
    """Open `original_path`, apply REFORMAT suggestions, save to `out_path`.

    `segment_ordinal_by_id` is the {segment.id → ordinal} map from the
    `ParseResult` — we need it to translate a Suggestion's segment_id
    (referenced inside `suggestion.range.segment_id`) back to a docx
    paragraph index.

    Suggestion kinds not yet supported (REPLACE / INSERT / DELETE) are
    skipped silently; v0 fix uses only auto-safe REFORMAT suggestions.
    """
    out_path = Path(out_path)
    docx_document = load_docx_document(str(original_path))

    paragraphs = list(docx_document.paragraphs)

    for suggestion in suggestions:
        if suggestion.kind is not SuggestionKind.REFORMAT:
            continue
        if suggestion.new_style is None:
            continue

        ordinal = segment_ordinal_by_id.get(suggestion.range.segment_id)
        if ordinal is None or ordinal >= len(paragraphs):
            continue

        _apply_observed_style(paragraphs[ordinal], suggestion.new_style)

    docx_document.save(str(out_path))
    return out_path


def _apply_observed_style(paragraph, style: ObservedStyle) -> None:
    """Push fields from an ObservedStyle onto a python-docx Paragraph.

    Each field is applied only if the suggestion actually specifies it
    (i.e. is not None). This lets a REFORMAT suggestion target one
    dimension (font size) without clobbering everything else.
    """
    if style.font_name is not None:
        for run in paragraph.runs:
            run.font.name = style.font_name
    if style.font_size_pt is not None:
        for run in paragraph.runs:
            run.font.size = Pt(style.font_size_pt)
    if style.bold is not None:
        for run in paragraph.runs:
            run.font.bold = style.bold
    if style.italic is not None:
        for run in paragraph.runs:
            run.font.italic = style.italic

    pf = paragraph.paragraph_format
    if style.line_spacing is not None:
        pf.line_spacing = style.line_spacing
    if style.indent_inches is not None:
        pf.first_line_indent = Inches(style.indent_inches)
    if style.alignment is not None:
        _apply_alignment(paragraph, style.alignment)


def _apply_alignment(paragraph, alignment: str) -> None:
    from docx.enum.text import WD_PARAGRAPH_ALIGNMENT

    mapping = {
        "left": WD_PARAGRAPH_ALIGNMENT.LEFT,
        "center": WD_PARAGRAPH_ALIGNMENT.CENTER,
        "right": WD_PARAGRAPH_ALIGNMENT.RIGHT,
        "justify": WD_PARAGRAPH_ALIGNMENT.JUSTIFY,
    }
    align = mapping.get(alignment.lower())
    if align is not None:
        paragraph.alignment = align
