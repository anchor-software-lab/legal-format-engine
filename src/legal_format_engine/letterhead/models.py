"""Letterhead data models."""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class LetterheadLine(BaseModel):
    text: str
    bold: bool = False
    italic: bool = False
    font_size_pt: float = 10.0
    alignment: str = "left"  # "left", "center", "right"


class Letterhead(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    lines: list[LetterheadLine] = Field(default_factory=list)
    logo_path: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
