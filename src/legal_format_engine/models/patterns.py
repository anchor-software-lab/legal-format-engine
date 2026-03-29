"""Pydantic models for brief formatting pattern analysis and learning."""

from __future__ import annotations

from pydantic import BaseModel


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
    font: FontPattern | None = None
    margins: MarginPattern | None = None
    line_spacing: float | None = None
    headings: list[HeadingPattern] = []
    sections: list[SectionPattern] = []
    paragraph_indent_inches: float | None = None
