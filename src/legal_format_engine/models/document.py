"""Internal document representation models."""

from __future__ import annotations

from enum import IntEnum, StrEnum

from pydantic import BaseModel


class HeadingLevel(IntEnum):
    """Heading hierarchy levels."""

    LEVEL_1 = 1  # ALL CAPS CENTERED
    LEVEL_2 = 2  # Roman numeral, title case
    LEVEL_3 = 3  # Capital letter, sentence case
    LEVEL_4 = 4  # Arabic numeral, sentence case


class Alignment(StrEnum):
    """Text alignment options."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"


class ContentBlock(BaseModel):
    """A paragraph or block of body text."""

    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    alignment: Alignment = Alignment.JUSTIFY


class Section(BaseModel):
    """A document section with heading and content."""

    id: str
    heading_text: str
    heading_level: HeadingLevel
    numbering_prefix: str | None = None
    content: list[ContentBlock] = []
    subsections: list[Section] = []
    is_generated: bool = False


class CaptionBlock(BaseModel):
    """The formatted caption at the top of the document."""

    lines: list[ContentBlock]


class SignatureBlock(BaseModel):
    """Attorney signature block."""

    attorney_name: str
    bar_number: str
    firm: str | None = None
    address: str
    phone: str
    email: str


class Severity(StrEnum):
    """Validation issue severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationIssue(BaseModel):
    """A single validation finding."""

    severity: Severity
    code: str
    message: str
    section_id: str | None = None
    auto_fixable: bool = False


class LegalDocument(BaseModel):
    """Top-level internal representation of a legal document."""

    metadata: dict | None = None
    caption: CaptionBlock | None = None
    sections: list[Section] = []
    signature_block: SignatureBlock | None = None
    certifications: list[Section] = []
    issues: list[ValidationIssue] = []
    raw_text: str | None = None
