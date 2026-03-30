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

The principle: an attorney who formats their brief with Times New Roman 12pt
and 1" margins should produce the same NormalizedDocument whether we ingest
the DOCX, print-to-PDF, or export from Google Docs.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


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


# ---------------------------------------------------------------------------
# Measurement snapping
# ---------------------------------------------------------------------------

# Standard margin values attorneys actually use (inches)
_STANDARD_MARGINS = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]

# Standard font sizes in legal documents (points)
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
    """Snap a margin measurement to standard legal margin values."""
    return snap_to_standard(value, _STANDARD_MARGINS, tolerance=0.12)


def snap_font_size(value: float) -> float:
    """Snap a font size to standard legal font sizes."""
    return snap_to_standard(value, _STANDARD_FONT_SIZES, tolerance=0.7)


def snap_line_spacing(value: float) -> float:
    """Snap a line spacing value to standard spacing."""
    return snap_to_standard(value, _STANDARD_LINE_SPACINGS, tolerance=0.25)


def snap_indent(value: float) -> float:
    """Snap an indentation value to standard indentation."""
    return snap_to_standard(value, _STANDARD_INDENTS, tolerance=0.1)


# ---------------------------------------------------------------------------
# Normalized document model
# ---------------------------------------------------------------------------

class NormalizedFont(BaseModel):
    """Canonical font specification after normalization."""
    family: str  # canonical family name ("Times New Roman", "Arial", etc.)
    size_pt: float  # snapped to standard size
    weight: float = 0.0  # proportion of document using this font (0-1)


class NormalizedMargins(BaseModel):
    """Canonical margin specification after normalization."""
    top: float
    bottom: float
    left: float
    right: float
    source_quality: str = "exact"  # "exact" (DOCX) or "estimated" (PDF)


class NormalizedHeading(BaseModel):
    """Canonical heading style after normalization."""
    level: int  # 1-4
    case_style: str  # "upper", "title", "sentence"
    alignment: str  # "center", "left"
    bold: bool
    font_size_pt: float | None = None
    numbering: str | None = None  # "roman", "alpha_upper", "alpha_lower", "arabic"
    sample_count: int = 0  # how many headings of this type were found


class NormalizedSection(BaseModel):
    """Canonical section identification."""
    id: str  # canonical section ID (e.g., "argument", "table_of_contents")
    original_name: str  # how it appeared in the source document
    order: int  # position in document (0-indexed)


class NormalizedParagraphStyle(BaseModel):
    """Canonical paragraph formatting for a specific context."""
    context: str  # "body", "block_quote", "footnote"
    font_family: str
    font_size_pt: float
    line_spacing: float
    first_line_indent: float = 0.0  # inches
    left_indent: float = 0.0  # inches
    alignment: str = "left"  # "left", "center", "right", "justify"
    space_before_pt: float = 0.0
    space_after_pt: float = 0.0


class NormalizedDocument(BaseModel):
    """Format-agnostic canonical representation of a legal document.

    This is what the ML layer sees. All format-specific quirks have been
    stripped. A DOCX and its print-to-PDF produce the same NormalizedDocument.
    """
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    source_filename: str
    source_format: str  # "docx", "pdf", "doc", "html"
    normalized_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # Metadata (user-tagged or auto-detected)
    jurisdiction: str | None = None
    court_level: str | None = None
    document_type: str | None = None

    # Attribution: who authored this document
    author: str | None = None  # individual attorney name
    firm: str | None = None  # law firm or organization

    # Quality score: how confident are we in the extracted formatting?
    # 1.0 = DOCX with explicit styles, 0.5 = PDF with estimated values
    extraction_confidence: float = 1.0

    # Core formatting
    primary_font: NormalizedFont | None = None
    secondary_fonts: list[NormalizedFont] = []
    margins: NormalizedMargins | None = None
    line_spacing: float | None = None  # snapped to standard value

    # Heading styles (one per detected level)
    heading_styles: list[NormalizedHeading] = []

    # Section structure
    sections: list[NormalizedSection] = []

    # Paragraph styles by context
    paragraph_styles: list[NormalizedParagraphStyle] = []

    # Indentation
    body_first_line_indent: float | None = None  # inches, snapped
    block_quote_indent: float | None = None  # inches, snapped

    # Document stats (for weighting)
    total_pages: int | None = None
    total_words: int | None = None
    total_paragraphs: int = 0
    total_headings: int = 0


# ---------------------------------------------------------------------------
# Normalizer
# ---------------------------------------------------------------------------

def normalize_brief_analysis(
    analysis: "BriefAnalysis",
    source_format: str = "unknown",
) -> NormalizedDocument:
    """Convert a BriefAnalysis (from brief_analyzer) to a NormalizedDocument.

    This is the bridge between the existing analysis pipeline and the ML layer.
    """
    from legal_format_engine.models.patterns import BriefAnalysis  # noqa: F811

    # Extraction confidence based on source format
    confidence = {
        "docx": 1.0,
        "pdf": 0.6,
        "doc": 0.4,
        "html": 0.7,
        "rtf": 0.3,
    }.get(source_format, 0.5)

    # Normalize fonts
    primary_font = None
    secondary_fonts = []
    if analysis.font_patterns:
        main = analysis.font_patterns[0]
        primary_font = NormalizedFont(
            family=canonicalize_font_name(main.font_name),
            size_pt=snap_font_size(main.font_size_pt),
            weight=1.0,
        )
        for fp in analysis.font_patterns[1:]:
            secondary_fonts.append(NormalizedFont(
                family=canonicalize_font_name(fp.font_name),
                size_pt=snap_font_size(fp.font_size_pt),
            ))

    # Normalize margins
    margins = None
    if analysis.margin_pattern:
        mp = analysis.margin_pattern
        quality = "exact" if source_format == "docx" else "estimated"
        margins = NormalizedMargins(
            top=snap_margin(mp.top),
            bottom=snap_margin(mp.bottom),
            left=snap_margin(mp.left),
            right=snap_margin(mp.right),
            source_quality=quality,
        )

    # Normalize line spacing
    line_spacing = None
    if analysis.line_spacing is not None:
        line_spacing = snap_line_spacing(analysis.line_spacing)

    # Normalize headings
    heading_styles = []
    for hp in analysis.heading_patterns:
        heading_styles.append(NormalizedHeading(
            level=hp.level,
            case_style=hp.case_style,
            alignment=hp.alignment,
            bold=hp.bold,
            font_size_pt=snap_font_size(hp.font_size_pt) if hp.font_size_pt else None,
            numbering=hp.numbering,
        ))

    # Normalize sections
    sections = []
    for sp in analysis.section_patterns:
        sections.append(NormalizedSection(
            id=sp.id,
            original_name=sp.common_names[0] if sp.common_names else sp.id,
            order=sp.typical_order,
        ))

    # Normalize indentation
    body_indent = None
    if analysis.paragraph_indent_inches is not None:
        body_indent = snap_indent(analysis.paragraph_indent_inches)

    bq_indent = None
    if analysis.block_quote_indent_inches is not None:
        bq_indent = snap_indent(analysis.block_quote_indent_inches)

    return NormalizedDocument(
        source_filename=analysis.source_filename,
        source_format=source_format,
        jurisdiction=analysis.jurisdiction,
        court_level=analysis.court_level,
        extraction_confidence=confidence,
        primary_font=primary_font,
        secondary_fonts=secondary_fonts,
        margins=margins,
        line_spacing=line_spacing,
        heading_styles=heading_styles,
        sections=sections,
        body_first_line_indent=body_indent,
        block_quote_indent=bq_indent,
    )


def normalize_from_docx(
    path: str,
    jurisdiction: str | None = None,
    court_level: str | None = None,
) -> NormalizedDocument:
    """Analyze a DOCX file and return a NormalizedDocument."""
    from legal_format_engine.analysis.brief_analyzer import analyze_brief
    analysis = analyze_brief(path, jurisdiction, court_level)
    doc = normalize_brief_analysis(analysis, source_format="docx")
    doc.jurisdiction = jurisdiction
    doc.court_level = court_level
    return doc


def normalize_from_pdf(
    path: str,
    jurisdiction: str | None = None,
    court_level: str | None = None,
) -> NormalizedDocument:
    """Analyze a PDF file and return a NormalizedDocument."""
    from legal_format_engine.analysis.brief_analyzer import analyze_brief
    analysis = analyze_brief(path, jurisdiction, court_level)
    doc = normalize_brief_analysis(analysis, source_format="pdf")
    doc.jurisdiction = jurisdiction
    doc.court_level = court_level
    return doc


def normalize_document(
    path: str,
    jurisdiction: str | None = None,
    court_level: str | None = None,
    document_type: str | None = None,
    author: str | None = None,
    firm: str | None = None,
) -> NormalizedDocument:
    """Normalize any supported document format.

    This is the main entry point. It detects the file type and routes
    to the appropriate normalizer.
    """
    from pathlib import Path as _Path
    from legal_format_engine.analysis.brief_analyzer import analyze_brief

    p = _Path(path)
    suffix = p.suffix.lower()

    format_map = {
        ".docx": "docx",
        ".pdf": "pdf",
        ".doc": "doc",
        ".htm": "html",
        ".html": "html",
        ".rtf": "rtf",
    }

    source_format = format_map.get(suffix, "unknown")

    if suffix in (".docx", ".pdf"):
        analysis = analyze_brief(str(p), jurisdiction, court_level)
        doc = normalize_brief_analysis(analysis, source_format=source_format)
    elif suffix == ".html" or suffix == ".htm":
        doc = _normalize_html(p, source_format)
    elif suffix == ".doc":
        doc = _normalize_legacy_doc(p, source_format)
    elif suffix == ".rtf":
        doc = _normalize_rtf(p, source_format)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    doc.jurisdiction = jurisdiction
    doc.court_level = court_level
    doc.document_type = document_type
    doc.author = author
    doc.firm = firm
    return doc


def _normalize_html(path, source_format: str) -> NormalizedDocument:
    """Normalize a Google Docs HTML export."""
    try:
        from legal_format_engine.analysis.gdocs_connector import GoogleDocsConnector
        result = GoogleDocsConnector.parse_html_export(path)
    except Exception:
        return NormalizedDocument(
            source_filename=path.name,
            source_format=source_format,
            extraction_confidence=0.3,
        )

    # Extract font info from parsed paragraphs
    font_counts: dict[str, int] = {}
    size_counts: dict[float, int] = {}
    for para in result.get("paragraphs", []):
        fname = para.get("font_family")
        fsize = para.get("font_size_pt")
        text_len = len(para.get("text", ""))
        if fname and text_len:
            font_counts[fname] = font_counts.get(fname, 0) + text_len
        if fsize and text_len:
            size_counts[fsize] = size_counts.get(fsize, 0) + text_len

    primary_font = None
    if font_counts and size_counts:
        top_font = max(font_counts, key=font_counts.get)
        top_size = max(size_counts, key=size_counts.get)
        primary_font = NormalizedFont(
            family=canonicalize_font_name(top_font),
            size_pt=snap_font_size(top_size),
            weight=1.0,
        )

    # Extract margins from page settings
    margins = None
    page = result.get("page_settings", {})
    if page.get("margin_top") is not None:
        margins = NormalizedMargins(
            top=snap_margin(page.get("margin_top", 1.0)),
            bottom=snap_margin(page.get("margin_bottom", 1.0)),
            left=snap_margin(page.get("margin_left", 1.0)),
            right=snap_margin(page.get("margin_right", 1.0)),
            source_quality="estimated",
        )

    return NormalizedDocument(
        source_filename=path.name,
        source_format=source_format,
        extraction_confidence=0.7,
        primary_font=primary_font,
        margins=margins,
    )


def _normalize_legacy_doc(path, source_format: str) -> NormalizedDocument:
    """Normalize a legacy .doc file by converting to DOCX first."""
    import subprocess
    import tempfile

    # Try libreoffice conversion
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "docx",
                 "--outdir", tmpdir, str(path)],
                capture_output=True, timeout=30, check=True,
            )
            from pathlib import Path as _Path
            converted = list(_Path(tmpdir).glob("*.docx"))
            if converted:
                from legal_format_engine.analysis.brief_analyzer import analyze_brief
                analysis = analyze_brief(str(converted[0]))
                doc = normalize_brief_analysis(analysis, source_format="doc")
                doc.extraction_confidence = 0.8  # conversion is pretty good
                return doc
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    # Fallback: minimal extraction
    return NormalizedDocument(
        source_filename=path.name,
        source_format=source_format,
        extraction_confidence=0.2,
    )


def _normalize_rtf(path, source_format: str) -> NormalizedDocument:
    """Normalize an RTF file."""
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "docx",
                 "--outdir", tmpdir, str(path)],
                capture_output=True, timeout=30, check=True,
            )
            from pathlib import Path as _Path
            converted = list(_Path(tmpdir).glob("*.docx"))
            if converted:
                from legal_format_engine.analysis.brief_analyzer import analyze_brief
                analysis = analyze_brief(str(converted[0]))
                doc = normalize_brief_analysis(analysis, source_format="rtf")
                doc.extraction_confidence = 0.7
                return doc
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    return NormalizedDocument(
        source_filename=path.name,
        source_format=source_format,
        extraction_confidence=0.2,
    )
