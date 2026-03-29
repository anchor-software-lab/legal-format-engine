"""Pydantic models defining the structure of a ruleset."""

from __future__ import annotations

from pydantic import BaseModel


class HeadingRule(BaseModel):
    """Formatting rules for a heading level."""

    level: int
    case_style: str  # "upper", "title", "sentence"
    alignment: str  # "center", "left"
    numbering: str | None = None  # "roman", "alpha_upper", "alpha_lower", "arabic"
    bold: bool = False


class RequiredSection(BaseModel):
    """A section required by the ruleset."""

    id: str
    canonical_name: str
    aliases: list[str] = []
    order: int
    required: bool = True
    heading_level: int = 1
    subsections: list[RequiredSection] = []
    # Group constraint: if set, at least one section in the same group
    # must be present. Use for "either combined or separate" patterns.
    # e.g., group="case_facts" means either the combined section or
    # both separate sections satisfy the requirement.
    group: str | None = None


class PageFormat(BaseModel):
    """Page layout and typography rules."""

    font_name: str = "Times New Roman"
    font_size_pt: float = 12
    line_spacing: float = 2.0
    margin_top_inches: float = 1.0
    margin_bottom_inches: float = 1.0
    margin_left_inches: float = 1.0
    margin_right_inches: float = 1.0
    page_width_inches: float = 8.5
    page_height_inches: float = 11.0


class CaptionRule(BaseModel):
    """Rules for generating a case caption."""

    court_line_style: str = "upper"  # casing for the court name line
    court_line_alignment: str = "center"
    case_number_alignment: str = "right"
    case_number_prefix: str = "Case No."
    party_separator: str = "v."
    party_name_style: str = "upper"
    party_role_style: str = "title"
    party_alignment: str = "center"
    party_role_indented: bool = False
    document_title_style: str = "upper"
    document_title_alignment: str = "center"
    include_district: bool = True
    include_appeal_from: bool = True
    appeal_from_style: str = "sentence"
    appeal_from_alignment: str = "center"


class SignatureBlock(BaseModel):
    """Signature block formatting rules."""

    template: str = ""


class CertificationRule(BaseModel):
    """A required certification block."""

    id: str
    title: str | None = None
    template: str


class Ruleset(BaseModel):
    """Complete ruleset for a specific jurisdiction/document type."""

    jurisdiction: str
    court_level: str
    document_type: str
    page_format: PageFormat = PageFormat()
    heading_rules: list[HeadingRule] = []
    required_sections: list[RequiredSection] = []
    caption_rule: CaptionRule = CaptionRule()
    certifications: list[CertificationRule] = []
    signature_block: SignatureBlock | None = None
    signature_block_required: bool = True

    def get_heading_rule(self, level: int) -> HeadingRule | None:
        """Look up heading rule by level."""
        for rule in self.heading_rules:
            if rule.level == level:
                return rule
        return None

    def get_section_aliases(self) -> dict[str, list[str]]:
        """Build a mapping of section_id -> [canonical_name, *aliases]."""
        result: dict[str, list[str]] = {}
        for section in self.required_sections:
            result[section.id] = [section.canonical_name, *section.aliases]
        return result
