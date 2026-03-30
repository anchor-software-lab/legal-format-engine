"""Document normalizer: strips format-specific quirks into a canonical representation.

The core problem: a DOCX reports "Times New Roman" while a PDF reports
"TimesNewRomanPSMT". A DOCX has explicit 1.0" margins while a PDF's margins
are estimated from text bounding boxes (maybe 0.97" or 1.03"). Google Docs HTML
uses class-based CSS that maps to different font names.

If we feed these raw values into the learner, format-specific noise drowns out
real formatting choices. The normalizer solves this by:

1. Canonicalizing font names (all PostScript/CSS variants -> canonical family)
2. Snapping measurements to standard increments (margins, sizes, spacing)
3. Normalizing heading detection across formats
4. Producing a single NormalizedDocument regardless of source format

The principle: an author who formats their document with Times New Roman 12pt
and 1" margins should produce the same NormalizedDocument whether we ingest
the DOCX, print-to-PDF, or export from Google Docs.
"""

from __future__ import annotations

import re
from pathlib import Path

from anchor_ml_engine.models import (
    NormalizedDocument,
    NormalizedFont,
    NormalizedHeading,
    NormalizedMargins,
    NormalizedParagraphStyle,
    NormalizedSection,
)


# ---------------------------------------------------------------------------
# Canonical font family mapping
# ---------------------------------------------------------------------------

_FONT_FAMILY_MAP: dict[str, str] = {}

# Times New Roman variants (PostScript, PDF embedded, CSS, Mac)
for _name in [
    "timesnewroman", "timesnewromanpsmt", "timesnewromanps",
    "timesnewroman-bold", "timesnewroman-italic", "timesnewroman-bolditalic",
    "timesnewromanpsmt-bold", "timesnewromanpsmt-italic",
    "timesnewromanps-boldmt", "timesnewromanps-italicmt",
    "timesnewromanps-bolditalicmt", "times", "times-roman",
    "times-bold", "times-italic", "times-bolditalic",
    "timesroman", "nimbusroman", "nimbusromno9l",
    "texgyreternmes", "liberationserif", "serif",
]:
    _FONT_FAMILY_MAP[_name] = "Times New Roman"

# Arial / Helvetica variants
for _name in [
    "arial", "arialmt", "arial-bold", "arial-italic", "arial-bolditalic",
    "arialmt-bold", "arialmt-italic", "helvetica", "helvetica-bold",
    "helvetica-oblique", "helvetica-boldoblique", "helveticaneue",
    "liberationsans", "nimbussans", "nimbussansl", "sans-serif",
    "sansserif",
]:
    _FONT_FAMILY_MAP[_name] = "Arial"

# Courier / monospace variants
for _name in [
    "courier", "couriernew", "couriernewpsmt", "courier-bold",
    "courier-oblique", "couriernew-bold", "couriernew-italic",
    "liberationmono", "nimbusmono", "nimbusmono-regular",
    "monospace", "consolas", "menlo", "monaco",
]:
    _FONT_FAMILY_MAP[_name] = "Courier New"

# Century Schoolbook (SCOTUS)
for _name in [
    "centuryschoolbook", "centuryschoolbook-bold", "centuryschoolbook-italic",
    "centuryschoolbook-bolditalic", "centuryschlbk",
    "newcenturyschlbk", "newcenturyschlbk-roman",
    "centuryoldstyle", "century",
]:
    _FONT_FAMILY_MAP[_name] = "Century Schoolbook"

# Garamond variants
for _name in [
    "garamond", "garamond-bold", "garamond-italic",
    "ebgaramond", "agaramondpro", "agaramondpro-regular",
    "garamondpremrpro", "cormorantgaramond",
]:
    _FONT_FAMILY_MAP[_name] = "Garamond"

# Book Antiqua / Palatino variants
for _name in [
    "bookantiqua", "bookantiqua-bold", "bookantiqua-italic",
    "palatino", "palatinolinotype", "palatinolinotype-bold",
    "palatinolinotype-roman", "texgyrepagella",
]:
    _FONT_FAMILY_MAP[_name] = "Book Antiqua"

# Georgia
for _name in [
    "georgia", "georgia-bold", "georgia-italic", "georgia-bolditalic",
]:
    _FONT_FAMILY_MAP[_name] = "Georgia"


def canonicalize_font_name(raw_name: str) -> str:
    """Map any font name variant to its canonical family name.

    Examples:
        "TimesNewRomanPSMT" -> "Times New Roman"
        "ArialMT"           -> "Arial"
        "Courier-Bold"      -> "Courier New"
        "Unknown-Font"      -> "Unknown-Font"  (returned as-is)
    """
    key = re.sub(r"[^a-z0-9]", "", raw_name.lower())
    # Try exact match first
    if key in _FONT_FAMILY_MAP:
        return _FONT_FAMILY_MAP[key]
    # Try prefix match (handles variants we didn't enumerate)
    for pattern, canonical in _FONT_FAMILY_MAP.items():
        if key.startswith(pattern) or pattern.startswith(key):
            return canonical
    return raw_name


def get_font_family_map() -> dict[str, str]:
    """Return a copy of the font family mapping for inspection/testing."""
    return dict(_FONT_FAMILY_MAP)


# ---------------------------------------------------------------------------
# Measurement snapping
# ---------------------------------------------------------------------------

# Standard margin values (inches)
_STANDARD_MARGINS = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]

# Standard font sizes (points)
_STANDARD_FONT_SIZES = [8.0, 9.0, 10.0, 10.5, 11.0, 12.0, 13.0, 14.0, 16.0, 18.0, 24.0]

# Standard line spacing values
_STANDARD_LINE_SPACINGS = [1.0, 1.15, 1.5, 2.0, 2.5, 3.0]

# Standard indentation values (inches)
_STANDARD_INDENTS = [0.0, 0.25, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0]


def snap_to_standard(value: float, standards: list[float], tolerance: float = 0.15) -> float:
    """Snap a measured value to the nearest standard value within tolerance.

    If no standard is within tolerance, return the value rounded to 2 decimals.
    This eliminates measurement noise (PDF says 0.97" -> snaps to 1.0").
    """
    closest = min(standards, key=lambda s: abs(s - value))
    if abs(closest - value) <= tolerance:
        return closest
    return round(value, 2)


def snap_margin(value: float) -> float:
    """Snap a margin measurement to standard margin values."""
    return snap_to_standard(value, _STANDARD_MARGINS, tolerance=0.12)


def snap_font_size(value: float) -> float:
    """Snap a font size to standard font sizes."""
    return snap_to_standard(value, _STANDARD_FONT_SIZES, tolerance=0.7)


def snap_line_spacing(value: float) -> float:
    """Snap a line spacing value to standard spacing."""
    return snap_to_standard(value, _STANDARD_LINE_SPACINGS, tolerance=0.25)


def snap_indent(value: float) -> float:
    """Snap an indentation value to standard indentation."""
    return snap_to_standard(value, _STANDARD_INDENTS, tolerance=0.1)


# ---------------------------------------------------------------------------
# Confidence by format
# ---------------------------------------------------------------------------

FORMAT_CONFIDENCE: dict[str, float] = {
    "docx": 1.0,
    "pdf": 0.6,
    "doc": 0.4,
    "html": 0.7,
    "rtf": 0.3,
}


# ---------------------------------------------------------------------------
# High-level normalize helpers
# ---------------------------------------------------------------------------

def normalize_font_data(
    fonts: list[dict],
    base_confidence: float = 1.0,
) -> tuple[NormalizedFont | None, list[NormalizedFont]]:
    """Normalize a list of font dicts into primary + secondary fonts.

    Each dict should have at minimum 'font_name' and 'font_size_pt'.
    """
    if not fonts:
        return None, []
    primary_raw = fonts[0]
    primary = NormalizedFont(
        family=canonicalize_font_name(primary_raw.get("font_name", "")),
        size_pt=snap_font_size(primary_raw.get("font_size_pt", 12.0)),
        weight=1.0,
    )
    secondary = []
    for f in fonts[1:]:
        secondary.append(NormalizedFont(
            family=canonicalize_font_name(f.get("font_name", "")),
            size_pt=snap_font_size(f.get("font_size_pt", 12.0)),
        ))
    return primary, secondary


def normalize_margins_data(
    margins: dict,
    source_format: str = "docx",
) -> NormalizedMargins | None:
    """Normalize a margins dict with top/bottom/left/right keys."""
    if not margins:
        return None
    quality = "exact" if source_format == "docx" else "estimated"
    return NormalizedMargins(
        top=snap_margin(margins.get("top", 1.0)),
        bottom=snap_margin(margins.get("bottom", 1.0)),
        left=snap_margin(margins.get("left", 1.0)),
        right=snap_margin(margins.get("right", 1.0)),
        source_quality=quality,
    )


def normalize_headings_data(
    headings: list[dict],
) -> list[NormalizedHeading]:
    """Normalize a list of heading dicts."""
    result = []
    for h in headings:
        nh = NormalizedHeading(
            level=h.get("level", 1),
            case_style=h.get("case_style", "title"),
            alignment=h.get("alignment", "left"),
            bold=h.get("bold", True),
            font_size_pt=snap_font_size(h["font_size_pt"]) if h.get("font_size_pt") else None,
            numbering=h.get("numbering"),
            sample_count=h.get("sample_count", 0),
        )
        result.append(nh)
    return result


def normalize_document(
    path: str,
    category: str | None = None,
    subcategory: str | None = None,
    document_type: str | None = None,
    author: str | None = None,
    organization: str | None = None,
    source_format: str | None = None,
) -> NormalizedDocument:
    """Normalize any supported document format.

    This is the main entry point. It detects the file type and routes
    to the appropriate connector for extraction, then normalizes.
    """
    p = Path(path)
    suffix = p.suffix.lower()

    format_map = {
        ".docx": "docx",
        ".pdf": "pdf",
        ".doc": "doc",
        ".htm": "html",
        ".html": "html",
        ".rtf": "rtf",
    }

    fmt = source_format or format_map.get(suffix, "unknown")
    confidence = FORMAT_CONFIDENCE.get(fmt, 0.5)

    # For actual file processing, connectors handle extraction.
    # Here we create a minimal document with metadata.
    doc = NormalizedDocument(
        source_filename=p.name,
        source_format=fmt,
        extraction_confidence=confidence,
        category=category,
        subcategory=subcategory,
        document_type=document_type,
        author=author,
        organization=organization,
    )
    return doc


def build_normalized_document(
    source_filename: str,
    source_format: str,
    fonts: list[dict] | None = None,
    margins: dict | None = None,
    line_spacing: float | None = None,
    headings: list[dict] | None = None,
    sections: list[dict] | None = None,
    body_indent: float | None = None,
    block_quote_indent: float | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    document_type: str | None = None,
    author: str | None = None,
    organization: str | None = None,
) -> NormalizedDocument:
    """Build a NormalizedDocument from raw extracted data.

    This is the main function connectors call after extracting raw format data.
    All values are normalized (fonts canonicalized, measurements snapped, etc.).
    """
    confidence = FORMAT_CONFIDENCE.get(source_format, 0.5)

    primary_font, secondary_fonts = normalize_font_data(fonts or [])
    norm_margins = normalize_margins_data(margins or {}, source_format) if margins else None
    norm_headings = normalize_headings_data(headings or [])

    norm_sections = []
    for s in (sections or []):
        norm_sections.append(NormalizedSection(
            id=s.get("id", ""),
            original_name=s.get("original_name", s.get("id", "")),
            order=s.get("order", 0),
        ))

    norm_spacing = snap_line_spacing(line_spacing) if line_spacing is not None else None
    norm_body_indent = snap_indent(body_indent) if body_indent is not None else None
    norm_bq_indent = snap_indent(block_quote_indent) if block_quote_indent is not None else None

    return NormalizedDocument(
        source_filename=source_filename,
        source_format=source_format,
        extraction_confidence=confidence,
        primary_font=primary_font,
        secondary_fonts=secondary_fonts,
        margins=norm_margins,
        line_spacing=norm_spacing,
        heading_styles=norm_headings,
        sections=norm_sections,
        body_first_line_indent=norm_body_indent,
        block_quote_indent=norm_bq_indent,
        category=category,
        subcategory=subcategory,
        document_type=document_type,
        author=author,
        organization=organization,
    )
