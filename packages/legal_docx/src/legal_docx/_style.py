"""Pull `ObservedStyle` off a python-docx paragraph.

python-docx exposes some properties (font, alignment) directly; for the
rest (margins from sectPr, indent details) we drop down to the underlying
WordprocessingML XML via lxml.
"""

from __future__ import annotations

from typing import Any

from docx.oxml.ns import qn

from legal_docx._units import (
    half_points_to_points,
    line_spacing_to_multiple,
    twips_to_inches,
)
from legal_quality_gate.types import ObservedStyle

_ALIGNMENT_MAP = {
    "left": "left",
    "start": "left",
    "center": "center",
    "right": "right",
    "end": "right",
    "both": "justify",
    "distribute": "justify",
}


def observed_style_for_paragraph(
    paragraph: Any, section_margins: dict[str, float | None]
) -> ObservedStyle:
    """Extract observed style from a python-docx Paragraph.

    Combines the first run's font properties with the paragraph's
    layout properties and the enclosing section's margins.
    """
    rPr = _first_run_rpr(paragraph)
    pPr = paragraph._p.find(qn("w:pPr"))

    return ObservedStyle(
        font_name=_font_name(rPr),
        font_size_pt=_font_size_pt(rPr),
        line_spacing=_line_spacing(pPr),
        alignment=_alignment(pPr),
        indent_inches=_first_line_indent_inches(pPr),
        bold=_bool_prop(rPr, "w:b"),
        italic=_bool_prop(rPr, "w:i"),
        margin_top_inches=section_margins.get("top"),
        margin_bottom_inches=section_margins.get("bottom"),
        margin_left_inches=section_margins.get("left"),
        margin_right_inches=section_margins.get("right"),
    )


def section_margins(section: Any) -> dict[str, float | None]:
    """Pull the margin dict (in inches) from a python-docx Section."""
    return {
        "top": _emu_to_inches(section.top_margin),
        "bottom": _emu_to_inches(section.bottom_margin),
        "left": _emu_to_inches(section.left_margin),
        "right": _emu_to_inches(section.right_margin),
    }


def _emu_to_inches(emu: Any) -> float | None:
    """python-docx margins are `Emu`/`Inches` objects with `.inches`."""
    if emu is None:
        return None
    try:
        return float(emu.inches)
    except AttributeError:
        return None


def _first_run_rpr(paragraph: Any):
    for run in paragraph.runs:
        rPr = run._r.find(qn("w:rPr"))
        if rPr is not None:
            return rPr
    return None


def _font_name(rPr) -> str | None:
    if rPr is None:
        return None
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        return None
    return rFonts.get(qn("w:ascii")) or rFonts.get(qn("w:hAnsi")) or rFonts.get(
        qn("w:cs")
    )


def _font_size_pt(rPr) -> float | None:
    if rPr is None:
        return None
    sz = rPr.find(qn("w:sz"))
    if sz is None:
        return None
    val = sz.get(qn("w:val"))
    try:
        return half_points_to_points(int(val))
    except (TypeError, ValueError):
        return None


def _line_spacing(pPr) -> float | None:
    if pPr is None:
        return None
    spacing = pPr.find(qn("w:spacing"))
    if spacing is None:
        return None
    line = spacing.get(qn("w:line"))
    line_rule = spacing.get(qn("w:lineRule"))
    try:
        return line_spacing_to_multiple(int(line) if line else None, line_rule)
    except (TypeError, ValueError):
        return None


def _alignment(pPr) -> str | None:
    if pPr is None:
        return None
    jc = pPr.find(qn("w:jc"))
    if jc is None:
        return None
    return _ALIGNMENT_MAP.get((jc.get(qn("w:val")) or "").lower())


def _first_line_indent_inches(pPr) -> float | None:
    if pPr is None:
        return None
    ind = pPr.find(qn("w:ind"))
    if ind is None:
        return None
    first_line = ind.get(qn("w:firstLine"))
    try:
        return twips_to_inches(int(first_line) if first_line else None)
    except (TypeError, ValueError):
        return None


def _bool_prop(rPr, qname: str) -> bool | None:
    if rPr is None:
        return None
    el = rPr.find(qn(qname))
    if el is None:
        return None
    val = el.get(qn("w:val"))
    if val is None:
        return True  # presence with no val attribute means "on"
    return val.lower() not in {"0", "false", "off"}
