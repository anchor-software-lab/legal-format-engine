"""Caption block model."""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from legal_format_engine.models.document import ContentBlock


class CaptionBlock(BaseModel):
    court_name: str = ""
    district: Optional[str] = None
    case_number: str = ""
    parties_left: list[ContentBlock] = Field(default_factory=list)
    document_title: str = ""
    lines: list[ContentBlock] = Field(default_factory=list)
