"""Pydantic models for brief formatting pattern analysis and learning."""

from __future__ import annotations

from uuid import uuid4

from pydantic import BaseModel, Field


class FontPattern(BaseModel):
    """Detected font usage pattern."""

    font_name: str
    font_size_pt: float
    confidence: float = 0.0  # 0-1, how many briefs agree


class MarginPattern(BaseModel):
    """Detected page margin pattern (inches)."""

    top: float
    bottom: float
    left: float
    right: float
    confidence: float = 0.0


class HeadingPattern(BaseModel):
    """Detected heading formatting pattern."""

    level: int
    case_style: str  # "upper", "title", "sentence"
    alignment: str  # "center", "left", "right", "justify"
    bold: bool
    font_size_pt: float | None = None
    numbering: str | None = None  # "roman", "alpha_upper", "arabic", etc.
    confidence: float = 0.0


class SectionPattern(BaseModel):
    """Detected section presence and ordering pattern."""

    id: str
    common_names: list[str]
    frequency: float = 0.0  # how often this section appears across briefs
    typical_order: int = 0


class ParagraphStyle(BaseModel):
    """Extracted paragraph formatting pattern."""

    context: str  # "body", "heading_1", "heading_2", "block_quote", "footnote", "caption"
    font_name: str | None = None
    font_size_pt: float | None = None
    bold: bool = False
    italic: bool = False
    underline: bool = False
    alignment: str = "left"  # left, center, right, justify
    line_spacing: float | None = None
    space_before_pt: float | None = None
    space_after_pt: float | None = None
    first_line_indent_inches: float | None = None
    left_indent_inches: float | None = None
    all_caps: bool = False


class PageNumbering(BaseModel):
    """Page numbering pattern."""

    position: str = "bottom"  # top, bottom
    alignment: str = "center"  # left, center, right
    format: str = "arabic"  # arabic, roman_lower, roman_upper
    start_page: int = 1
    skip_first: bool = False  # skip numbering on title/caption page


class HeaderFooter(BaseModel):
    """Header/footer pattern."""

    has_header: bool = False
    has_footer: bool = False
    header_content: str | None = None
    footer_content: str | None = None


class DocumentStructure(BaseModel):
    """Overall document structure analysis."""

    has_caption_page: bool = False
    has_table_of_contents: bool = False
    has_table_of_authorities: bool = False
    has_signature_block: bool = False
    has_certifications: bool = False
    section_order: list[str] = []  # ordered list of detected section IDs
    total_pages: int | None = None
    total_words: int | None = None


class ProcessedDocument(BaseModel):
    """Complete analysis of an uploaded document."""

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    original_filename: str
    file_type: str  # "docx", "pdf", "doc", "html", "rtf"
    file_size_bytes: int = 0
    uploaded_at: str  # ISO datetime
    jurisdiction: str | None = None
    court_level: str | None = None
    document_type: str | None = None  # "brief", "motion", "petition", etc.
    court_name: str | None = None  # auto-detected or user-provided

    # Quality flags
    full_formatting_extracted: bool = True  # False if only text was extractable
    processing_warnings: list[str] = []

    # Extracted patterns
    margin_pattern: MarginPattern | None = None
    paragraph_styles: list[ParagraphStyle] = []
    heading_patterns: list[HeadingPattern] = []
    page_numbering: PageNumbering | None = None
    header_footer: HeaderFooter | None = None
    document_structure: DocumentStructure | None = None

    # Raw section data
    detected_sections: list[SectionPattern] = []

    # Tags for organizing
    tags: list[str] = []  # user-provided tags like "good_example", "7th_circuit", etc.
    notes: str | None = None  # user notes about this document


class BriefAnalysis(BaseModel):
    """Complete formatting analysis of a single uploaded brief."""

    id: str
    source_filename: str
    jurisdiction: str | None = None
    court_level: str | None = None
    analyzed_at: str  # ISO datetime
    font_patterns: list[FontPattern] = []
    margin_pattern: MarginPattern | None = None
    line_spacing: float | None = None
    heading_patterns: list[HeadingPattern] = []
    section_patterns: list[SectionPattern] = []
    paragraph_indent_inches: float | None = None
    block_quote_indent_inches: float | None = None


class AggregatePatterns(BaseModel):
    """Aggregated formatting patterns across multiple briefs for a jurisdiction."""

    jurisdiction: str
    court_level: str | None = None
    brief_count: int = 0
    document_count: int = 0
    font: FontPattern | None = None
    margins: MarginPattern | None = None
    line_spacing: float | None = None
    headings: list[HeadingPattern] = []
    sections: list[SectionPattern] = []
    paragraph_indent_inches: float | None = None
    paragraph_styles: list[ParagraphStyle] = []
    page_numbering: PageNumbering | None = None
