"""Section and ruleset models."""

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class HeadingLevel(str, Enum):
    ALL_CAPS_CENTERED = "all_caps_centered"
    ALL_CAPS_LEFT = "all_caps_left"
    TITLE_CASE_CENTERED = "title_case_centered"
    TITLE_CASE_LEFT = "title_case_left"
    ROMAN_NUMERAL = "roman_numeral"
    CAPITAL_LETTER = "capital_letter"
    ARABIC_NUMERAL = "arabic_numeral"
    SENTENCE_CASE = "sentence_case"


class HeadingRule(BaseModel):
    level: int
    style: HeadingLevel
    bold: bool = True
    centered: bool = False
    indent_inches: float = 0.0


class PageFormat(BaseModel):
    font: str = "Times New Roman"
    font_size_pt: float = 13.0
    line_spacing: str = "double"
    margin_top_inches: float = 1.0
    margin_bottom_inches: float = 1.0
    margin_left_inches: float = 1.0
    margin_right_inches: float = 1.0
    page_width_inches: float = 8.5
    page_height_inches: float = 11.0
    first_line_indent_inches: float = 0.5
    hyphenation: bool = True


class SectionRule(BaseModel):
    section_type: str
    title: Optional[str] = None
    required: bool = True
    order: int = 0
    heading_level: int = 1
    aliases: list[str] = Field(default_factory=list)
    group: Optional[str] = None


class CertificationTemplate(BaseModel):
    cert_type: str
    title: Optional[str] = None
    template: str
    required: bool = True


class Ruleset(BaseModel):
    name: str
    jurisdiction: str
    court_level: str
    document_type: str
    description: Optional[str] = None
    statute_reference: Optional[str] = None
    page_format: PageFormat = Field(default_factory=PageFormat)
    heading_rules: list[HeadingRule] = Field(default_factory=list)
    section_rules: list[SectionRule] = Field(default_factory=list)
    certification_templates: list[CertificationTemplate] = Field(default_factory=list)
    page_limit: Optional[int] = None
    word_limit: Optional[int] = None
    allow_combined_case_facts: bool = False
