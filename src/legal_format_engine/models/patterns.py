"""ML pattern models for brief analysis."""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class FontPattern(BaseModel):
    font_name: str
    font_size_pt: float
    bold: bool = False
    italic: bool = False
    frequency: int = 1
    confidence: float = 1.0


class MarginPattern(BaseModel):
    top_inches: float = 1.0
    bottom_inches: float = 1.0
    left_inches: float = 1.0
    right_inches: float = 1.0
    confidence: float = 1.0


class HeadingPattern(BaseModel):
    text: str
    level: int = 1
    style: str = ""
    font_name: Optional[str] = None
    font_size_pt: Optional[float] = None
    bold: bool = False
    centered: bool = False
    all_caps: bool = False


class SectionPattern(BaseModel):
    section_type: str
    heading_text: str
    order: int = 0
    present: bool = True


class FormatProfile(BaseModel):
    fonts: list[FontPattern] = Field(default_factory=list)
    margins: Optional[MarginPattern] = None
    headings: list[HeadingPattern] = Field(default_factory=list)
    sections: list[SectionPattern] = Field(default_factory=list)
    line_spacing: Optional[str] = None
    first_line_indent_inches: Optional[float] = None
    source_format: str = "unknown"
    confidence: float = 1.0
    author: Optional[str] = None
    firm: Optional[str] = None


class BriefAnalysis(BaseModel):
    file_name: str
    file_path: Optional[str] = None
    jurisdiction: Optional[str] = None
    court_level: Optional[str] = None
    document_type: Optional[str] = None
    profile: FormatProfile = Field(default_factory=FormatProfile)
    tags: list[str] = Field(default_factory=list)
