"""FastAPI server exposing the legal format engine as REST endpoints."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from legal_format_engine.api.schemas import (
    CitationInfo,
    CitationIssueInfo,
    CitationRequest,
    CitationResponse,
    FormatRequest,
    FormatResponse,
    HealthResponse,
    SectionSummary,
    ValidateRequest,
    ValidateResponse,
)
from legal_format_engine.engines.citation_engine import check_citation_consistency
from legal_format_engine.engines.pipeline import format_document
from legal_format_engine.renderers.docx_renderer import render_docx
from legal_format_engine.renderers.markdown_renderer import render_markdown
from legal_format_engine.models.metadata import DocumentMetadata
from legal_format_engine.rules.loader import load_ruleset

app = FastAPI(
    title="Legal Format Engine API",
    description="Rules-based legal document formatting engine for Wisconsin appellate briefs.",
    version="0.1.0",
)

# CORS for Word Add-in and web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://localhost:3000",
        "https://localhost:3443",
        "null",  # Office Add-in sideloaded
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _extract_text_from_upload(file: UploadFile) -> str:
    """Read uploaded file and extract text content."""
    content = file.file.read()
    suffix = Path(file.filename or "input.txt").suffix.lower()

    if suffix == ".docx":
        tmp = Path(tempfile.mktemp(suffix=".docx"))
        tmp.write_bytes(content)
        from legal_format_engine.parsers.docx_parser import parse_docx
        doc = parse_docx(tmp)
        tmp.unlink(missing_ok=True)
        return doc.raw_text or ""
    elif suffix == ".pdf":
        tmp = Path(tempfile.mktemp(suffix=".pdf"))
        tmp.write_bytes(content)
        from legal_format_engine.parsers.pdf_parser import parse_pdf
        doc = parse_pdf(tmp)
        tmp.unlink(missing_ok=True)
        return doc.raw_text or ""
    else:
        return content.decode("utf-8")


def _sections_summary(doc) -> list[SectionSummary]:
    return [
        SectionSummary(
            id=s.id,
            heading=s.heading_text,
            level=s.heading_level,
            is_generated=s.is_generated,
            content_length=sum(len(b.text) for b in s.content),
        )
        for s in doc.sections
    ]


# ── Health ────────────────────────────────────────────────────────────


@app.get("/api/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", version="0.1.0")


# ── Format (JSON body) ───────────────────────────────────────────────


@app.post("/api/format")
async def format_json(req: FormatRequest):
    """Format a document from JSON request body.

    Returns DOCX file download when output_format='docx',
    or JSON with markdown when output_format='markdown'.
    """
    try:
        ruleset = load_ruleset(req.jurisdiction, req.court_level, req.document_type,
                               variant=req.variant)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    doc = format_document(
        req.text, req.metadata, ruleset,
        word_count=req.word_count,
        insert_missing=req.insert_missing,
    )

    if req.output_format == "docx":
        output = Path(tempfile.mktemp(suffix=".docx"))
        path = render_docx(doc, ruleset, str(output))
        return FileResponse(
            path=str(path),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename="formatted_brief.docx",
            headers={"X-Issues-Count": str(len(doc.issues))},
        )
    else:
        md = render_markdown(doc)
        return FormatResponse(
            markdown=md,
            issue_count=len(doc.issues),
            issues=doc.issues,
            sections=_sections_summary(doc),
        )


# ── Format (File upload) ─────────────────────────────────────────────


@app.post("/api/format/upload")
async def format_upload(
    file: UploadFile = File(...),
    metadata_json: str = Form(...),
    jurisdiction: str = Form("wisconsin"),
    court_level: str = Form("appellate"),
    document_type: str = Form("brief"),
    variant: str | None = Form(None),
    output_format: str = Form("docx"),
    word_count: int | None = Form(None),
    insert_missing: bool = Form(True),
):
    """Format an uploaded DOCX/PDF/text file.

    Accepts multipart form data with the file and metadata JSON string.
    """
    try:
        meta = DocumentMetadata.model_validate_json(metadata_json)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid metadata: {e}")

    text = _extract_text_from_upload(file)

    try:
        ruleset = load_ruleset(jurisdiction, court_level, document_type, variant=variant)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    doc = format_document(
        text, meta, ruleset,
        word_count=word_count,
        insert_missing=insert_missing,
    )

    if output_format == "docx":
        output = Path(tempfile.mktemp(suffix=".docx"))
        path = render_docx(doc, ruleset, str(output))
        return FileResponse(
            path=str(path),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename="formatted_brief.docx",
        )
    else:
        md = render_markdown(doc)
        return FormatResponse(
            markdown=md,
            issue_count=len(doc.issues),
            issues=doc.issues,
            sections=_sections_summary(doc),
        )


# ── Validate ──────────────────────────────────────────────────────────


@app.post("/api/validate", response_model=ValidateResponse)
async def validate(req: ValidateRequest):
    """Validate document structure without formatting."""
    try:
        ruleset = load_ruleset(req.jurisdiction, req.court_level, req.document_type,
                               variant=req.variant)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    doc = format_document(req.text, req.metadata, ruleset, insert_missing=False)

    return ValidateResponse(
        valid=len(doc.issues) == 0,
        issue_count=len(doc.issues),
        issues=doc.issues,
        sections=_sections_summary(doc),
    )


# ── Validate (File upload) ───────────────────────────────────────────


@app.post("/api/validate/upload", response_model=ValidateResponse)
async def validate_upload(
    file: UploadFile = File(...),
    metadata_json: str = Form(...),
    jurisdiction: str = Form("wisconsin"),
    court_level: str = Form("appellate"),
    document_type: str = Form("brief"),
    variant: str | None = Form(None),
):
    """Validate an uploaded document."""
    try:
        meta = DocumentMetadata.model_validate_json(metadata_json)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid metadata: {e}")

    text = _extract_text_from_upload(file)

    try:
        ruleset = load_ruleset(jurisdiction, court_level, document_type, variant=variant)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    doc = format_document(text, meta, ruleset, insert_missing=False)

    return ValidateResponse(
        valid=len(doc.issues) == 0,
        issue_count=len(doc.issues),
        issues=doc.issues,
        sections=_sections_summary(doc),
    )


# ── Citations ─────────────────────────────────────────────────────────


@app.post("/api/citations", response_model=CitationResponse)
async def citations(req: CitationRequest):
    """Check citation consistency in text."""
    report = check_citation_consistency(req.text)

    cases = sum(1 for c in report.citations if c.citation_type.value == "case")
    short_cites = sum(1 for c in report.citations if c.citation_type.value == "short_cite")
    ids = sum(1 for c in report.citations if c.citation_type.value == "id")

    return CitationResponse(
        total_citations=len(report.citations),
        cases=cases,
        short_cites=short_cites,
        id_references=ids,
        statutes=len(report.statute_citations),
        issues=[
            CitationIssueInfo(
                code=i.code,
                severity=i.severity.value,
                message=i.message,
                suggestion=i.suggestion,
            )
            for i in report.issues
        ],
    )


# ── Citations (File upload) ───────────────────────────────────────────


@app.post("/api/citations/upload", response_model=CitationResponse)
async def citations_upload(file: UploadFile = File(...)):
    """Check citation consistency in an uploaded file."""
    text = _extract_text_from_upload(file)
    report = check_citation_consistency(text)

    cases = sum(1 for c in report.citations if c.citation_type.value == "case")
    short_cites = sum(1 for c in report.citations if c.citation_type.value == "short_cite")
    ids = sum(1 for c in report.citations if c.citation_type.value == "id")

    return CitationResponse(
        total_citations=len(report.citations),
        cases=cases,
        short_cites=short_cites,
        id_references=ids,
        statutes=len(report.statute_citations),
        issues=[
            CitationIssueInfo(
                code=i.code,
                severity=i.severity.value,
                message=i.message,
                suggestion=i.suggestion,
            )
            for i in report.issues
        ],
    )
