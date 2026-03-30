"""ML Document Normalizer - strips format-specific quirks to create equal representations."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import re

# Font name normalization map
_FONT_ALIASES = {
    "timesnewromanpsmt": "Times New Roman",
    "timesnewroman": "Times New Roman",
    "times": "Times New Roman",
    "timesroman": "Times New Roman",
    "timesbold": "Times New Roman",
    "timesitalic": "Times New Roman",
    "timesbolditalic": "Times New Roman",
    "arial": "Arial",
    "arialmt": "Arial",
    "arialboldmt": "Arial",
    "helvetica": "Helvetica",
    "helveticabold": "Helvetica",
    "couriernewest": "Courier New",
    "couriernewpsmt": "Courier New",
    "courier": "Courier New",
    "centuryschoolbook": "Century Schoolbook",
    "centuryschlbk": "Century Schoolbook",
    "centuryschlbkbt": "Century Schoolbook",
    "garamond": "Garamond",
    "garamondbold": "Garamond",
    "bookantiqua": "Book Antiqua",
    "palatino": "Palatino",
    "palatinolinotype": "Palatino",
    "cambria": "Cambria",
    "georgia": "Georgia",
    "calibri": "Calibri",
    "calibribold": "Calibri",
}

# Standard legal margin values for snapping
_STANDARD_MARGINS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
_STANDARD_FONT_SIZES = [8, 9, 10, 10.5, 11, 12, 13, 14, 16, 18, 20, 24]
_STANDARD_LINE_SPACINGS = [1.0, 1.15, 1.5, 2.0]

# Format confidence scores
FORMAT_CONFIDENCE = {
    "docx": 1.0,
    "pdf": 0.6,
    "html": 0.7,
    "doc": 0.4,
    "rtf": 0.5,
    "txt": 0.3,
}


@dataclass
class NormalizedDocument:
    """Format-agnostic document representation for ML processing."""
    file_name: str = ""
    source_format: str = "unknown"
    confidence: float = 1.0
    font_name: Optional[str] = None
    font_size_pt: Optional[float] = None
    margin_top: Optional[float] = None
    margin_bottom: Optional[float] = None
    margin_left: Optional[float] = None
    margin_right: Optional[float] = None
    line_spacing: Optional[float] = None
    first_line_indent: Optional[float] = None
    heading_styles: list[dict] = field(default_factory=list)
    section_names: list[str] = field(default_factory=list)
    jurisdiction: Optional[str] = None
    court_level: Optional[str] = None
    document_type: Optional[str] = None
    author: Optional[str] = None
    firm: Optional[str] = None
    tags: list[str] = field(default_factory=list)


def normalize_font_name(name: str) -> str:
    """Normalize font name to canonical form."""
    key = re.sub(r"[^a-z]", "", name.lower())
    return _FONT_ALIASES.get(key, name)


def snap_to_standard(value: float, standards: list[float], tolerance: float = 0.15) -> float:
    """Snap a value to the nearest standard value if within tolerance."""
    if value is None:
        return value
    for std in standards:
        if abs(value - std) <= tolerance:
            return std
    return round(value, 2)


def normalize_document(
    profile: dict,
    source_format: str = "unknown",
    file_name: str = "",
    author: Optional[str] = None,
    firm: Optional[str] = None,
) -> NormalizedDocument:
    """Normalize a format profile into a NormalizedDocument.

    Strips format-specific quirks:
    - Font names mapped to canonical forms
    - Margins snapped to standard values
    - Font sizes snapped to standard values
    - Line spacing snapped to standard values
    """
    confidence = FORMAT_CONFIDENCE.get(source_format, 0.5)

    # Font normalization
    font_name = None
    font_size = None
    if "fonts" in profile and profile["fonts"]:
        raw_font = profile["fonts"][0] if isinstance(profile["fonts"][0], dict) else None
        if raw_font:
            font_name = normalize_font_name(raw_font.get("font_name", ""))
            raw_size = raw_font.get("font_size_pt", 0)
            font_size = snap_to_standard(raw_size, _STANDARD_FONT_SIZES) if raw_size else None

    # Margin normalization
    margins = profile.get("margins", {})
    margin_top = snap_to_standard(margins.get("top_inches", margins.get("top")), _STANDARD_MARGINS) if margins else None
    margin_bottom = snap_to_standard(margins.get("bottom_inches", margins.get("bottom")), _STANDARD_MARGINS) if margins else None
    margin_left = snap_to_standard(margins.get("left_inches", margins.get("left")), _STANDARD_MARGINS) if margins else None
    margin_right = snap_to_standard(margins.get("right_inches", margins.get("right")), _STANDARD_MARGINS) if margins else None

    # Line spacing
    raw_spacing = profile.get("line_spacing")
    line_spacing = None
    if raw_spacing:
        if isinstance(raw_spacing, str):
            if raw_spacing == "double":
                line_spacing = 2.0
            elif raw_spacing == "single":
                line_spacing = 1.0
            else:
                try:
                    line_spacing = snap_to_standard(float(raw_spacing), _STANDARD_LINE_SPACINGS)
                except ValueError:
                    pass
        else:
            line_spacing = snap_to_standard(float(raw_spacing), _STANDARD_LINE_SPACINGS)

    # Heading styles
    heading_styles = []
    for h in profile.get("headings", []):
        if isinstance(h, dict):
            heading_styles.append({
                "text": h.get("text", ""),
                "level": h.get("level", 1),
                "bold": h.get("bold", False),
                "centered": h.get("centered", False),
                "all_caps": h.get("all_caps", False),
            })

    # Sections
    section_names = []
    for s in profile.get("sections", []):
        if isinstance(s, dict):
            section_names.append(s.get("heading_text", s.get("section_type", "")))

    return NormalizedDocument(
        file_name=file_name,
        source_format=source_format,
        confidence=confidence,
        font_name=font_name,
        font_size_pt=font_size,
        margin_top=margin_top,
        margin_bottom=margin_bottom,
        margin_left=margin_left,
        margin_right=margin_right,
        line_spacing=line_spacing,
        first_line_indent=profile.get("first_line_indent_inches"),
        heading_styles=heading_styles,
        section_names=section_names,
        jurisdiction=profile.get("jurisdiction"),
        court_level=profile.get("court_level"),
        document_type=profile.get("document_type"),
        author=author,
        firm=firm,
        tags=profile.get("tags", []),
    )
