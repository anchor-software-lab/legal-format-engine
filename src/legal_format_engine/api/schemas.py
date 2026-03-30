"""Request and response schemas for the API."""

from __future__ import annotations

from pydantic import BaseModel

from legal_format_engine.models.document import (
    Severity,
    ValidationIssue,
)
from legal_format_engine.models.metadata import DocumentMetadata


class FormatRequest(BaseModel):
    """Request body for /api/format (JSON mode)."""

    text: str
    metadata: DocumentMetadata
    jurisdiction: str = "wisconsin"
    court_level: str = "appellate"
    document_type: str = "brief"
    variant: str | None = None
    output_format: str = "docx"  # "docx" or "markdown"
    word_count: int | None = None
    insert_missing: bool = True
    letterhead_id: str | None = None  # ID of saved letterhead to apply


class ValidateRequest(BaseModel):
    """Request body for /api/validate."""

    text: str
    metadata: DocumentMetadata
    jurisdiction: str = "wisconsin"
    court_level: str = "appellate"
    document_type: str = "brief"
    variant: str | None = None


class ValidateResponse(BaseModel):
    """Response for /api/validate."""

    valid: bool
    issue_count: int
    issues: list[ValidationIssue]
    sections: list[SectionSummary]


class SectionSummary(BaseModel):
    """Lightweight section info for API responses."""

    id: str
    heading: str
    level: int
    is_generated: bool = False
    content_length: int = 0


class CitationRequest(BaseModel):
    """Request body for /api/citations."""

    text: str


class CitationInfo(BaseModel):
    """Single citation found in text."""

    text: str
    citation_type: str
    position: int


class CitationIssueInfo(BaseModel):
    """Single citation issue."""

    code: str
    severity: str
    message: str
    suggestion: str | None = None


class CitationResponse(BaseModel):
    """Response for /api/citations."""

    total_citations: int
    cases: int
    short_cites: int
    id_references: int
    statutes: int
    issues: list[CitationIssueInfo]


class FormatResponse(BaseModel):
    """Response for /api/format when output_format is markdown."""

    markdown: str
    issue_count: int
    issues: list[ValidationIssue]
    sections: list[SectionSummary]


class HealthResponse(BaseModel):
    """Response for /api/health."""

    status: str
    version: str


class LetterheadLineSchema(BaseModel):
    """A single line in a letterhead."""

    text: str
    bold: bool = False
    italic: bool = False
    font_size_pt: float | None = None
    alignment: str = "center"


class LetterheadCreate(BaseModel):
    """Request body to create/update a letterhead."""

    name: str
    lines: list[LetterheadLineSchema] = []
    logo_width_inches: float = 1.5
    separator_line: bool = True
    spacing_after_pt: float = 12.0


class LetterheadResponse(BaseModel):
    """Response for a single letterhead."""

    id: str
    name: str
    lines: list[LetterheadLineSchema]
    logo_path: str | None = None
    logo_width_inches: float = 1.5
    separator_line: bool = True
    spacing_after_pt: float = 12.0


class LetterheadListResponse(BaseModel):
    """Response for listing letterheads."""

    letterheads: list[LetterheadResponse]


# ── Brief Analysis Schemas ───────────────────────────────────────────


class BriefUploadResponse(BaseModel):
    """Response after uploading and analyzing a brief."""

    id: str
    source_filename: str
    jurisdiction: str | None = None
    court_level: str | None = None
    analyzed_at: str
    font_patterns: list[dict] = []
    margin_pattern: dict | None = None
    line_spacing: float | None = None
    heading_patterns: list[dict] = []
    section_patterns: list[dict] = []
    paragraph_indent_inches: float | None = None
    block_quote_indent_inches: float | None = None


class BriefAnalysisListResponse(BaseModel):
    """Response listing all analyzed briefs."""

    analyses: list[BriefUploadResponse]
    total: int


class AggregatePatternResponse(BaseModel):
    """Response with aggregated patterns for a jurisdiction."""

    jurisdiction: str
    court_level: str | None = None
    brief_count: int = 0
    font: dict | None = None
    margins: dict | None = None
    line_spacing: float | None = None
    headings: list[dict] = []
    sections: list[dict] = []
    paragraph_indent_inches: float | None = None


class GoogleDocUploadResponse(BaseModel):
    """Response after uploading a Google Doc for analysis."""

    id: str
    source_filename: str
    source_url: str
    jurisdiction: str | None = None
    court_level: str | None = None
    document_type: str | None = None
    analyzed_at: str
    font_patterns: list[dict] = []
    margin_pattern: dict | None = None
    line_spacing: float | None = None
    heading_patterns: list[dict] = []
    section_patterns: list[dict] = []
    paragraph_indent_inches: float | None = None
    block_quote_indent_inches: float | None = None
    tags: str | None = None
    notes: str | None = None


# Rebuild models that reference forward declarations
ValidateResponse.model_rebuild()
