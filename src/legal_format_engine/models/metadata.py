"""Case and document metadata models."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel


class PartyRole(StrEnum):
    """Roles a party can have in a case."""

    DEFENDANT_APPELLANT = "defendant-appellant"
    PLAINTIFF_RESPONDENT = "plaintiff-respondent"
    STATE_RESPONDENT = "state-respondent"
    STATE_PLAINTIFF = "state-plaintiff"
    PETITIONER = "petitioner"
    RESPONDENT = "respondent"
    APPELLANT = "appellant"


class Party(BaseModel):
    """A party in the case."""

    name: str
    role: PartyRole


class AttorneyInfo(BaseModel):
    """Attorney identification and contact information."""

    name: str
    bar_number: str
    firm: str | None = None
    address: str
    phone: str
    email: str


class CaseMetadata(BaseModel):
    """Core case identification."""

    case_number: str
    court_name: str
    county_of_origin: str | None = None
    circuit_court_case_number: str | None = None
    judge_name: str | None = None
    district: str | None = None
    parties: list[Party]


class DocumentMetadata(BaseModel):
    """Full metadata needed to format a legal document."""

    jurisdiction: str
    court_level: str
    document_type: str
    case: CaseMetadata
    document_title: str
    attorney: AttorneyInfo
    date_filed: date | None = None
