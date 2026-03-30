"""Core document data models."""

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class PartyRole(str, Enum):
    PLAINTIFF = "plaintiff"
    DEFENDANT = "defendant"
    APPELLANT = "appellant"
    RESPONDENT = "respondent"
    PETITIONER = "petitioner"
    INTERVENOR = "intervenor"
    AMICUS = "amicus"


class Party(BaseModel):
    name: str
    role: PartyRole
    designation: Optional[str] = None  # e.g. "Plaintiff-Respondent"


class Attorney(BaseModel):
    name: str
    bar_number: Optional[str] = None
    firm: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_lead: bool = False


class CaseMetadata(BaseModel):
    case_name: str
    case_number: str
    court_name: Optional[str] = None
    district: Optional[str] = None
    county: Optional[str] = None
    judge: Optional[str] = None
    parties: list[Party] = Field(default_factory=list)
    attorneys: list[Attorney] = Field(default_factory=list)


class DocumentMetadata(BaseModel):
    jurisdiction: str = "wisconsin"
    court_level: str = "court_of_appeals"
    document_type: str = "appellate_brief"
    document_title: Optional[str] = None
    variant: Optional[str] = None


class ContentBlock(BaseModel):
    text: str
    style: Optional[str] = None
    bold: bool = False
    italic: bool = False
    centered: bool = False
    font_size_pt: Optional[float] = None
    is_heading: bool = False
    heading_level: int = 0
    is_body_text: bool = False
    is_caption: bool = False
    is_page_break: bool = False
    numbering_prefix: Optional[str] = None


class Section(BaseModel):
    section_type: str
    heading: str
    heading_level: int = 1
    content: list[ContentBlock] = Field(default_factory=list)
    subsections: list["Section"] = Field(default_factory=list)
    numbering_prefix: Optional[str] = None
    order_index: Optional[int] = None
    is_stub: bool = False


class DocumentModel(BaseModel):
    metadata: DocumentMetadata
    case_metadata: Optional[CaseMetadata] = None
    caption: Optional["CaptionBlock"] = None
    sections: list[Section] = Field(default_factory=list)
    certifications: list[Section] = Field(default_factory=list)
    signature_block: Optional[Section] = None
    format_profile: Optional[dict] = None


# Avoid circular import
from legal_format_engine.models.caption import CaptionBlock  # noqa: E402

DocumentModel.model_rebuild()
Section.model_rebuild()
