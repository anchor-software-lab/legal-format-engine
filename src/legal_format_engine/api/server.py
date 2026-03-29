"""FastAPI server exposing the legal format engine as REST endpoints."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from legal_format_engine.api.schemas import (
    AggregatePatternResponse,
    BriefAnalysisListResponse,
    BriefUploadResponse,
    CitationInfo,
    CitationIssueInfo,
    CitationRequest,
    CitationResponse,
    FormatRequest,
    FormatResponse,
    GoogleDocUploadResponse,
    HealthResponse,
    LetterheadCreate,
    LetterheadListResponse,
    LetterheadResponse,
    SectionSummary,
    ValidateRequest,
    ValidateResponse,
)
from legal_format_engine.analysis.brief_analyzer import analyze_brief
from legal_format_engine.analysis.gdocs_connector import GoogleDocsConnector
from legal_format_engine.analysis.pattern_store import PatternStore
from legal_format_engine.engines.citation_engine import check_citation_consistency
from legal_format_engine.engines.pipeline import format_document
from legal_format_engine.models.letterhead import Letterhead, LetterheadLine, LetterheadManager
from legal_format_engine.models.metadata import DocumentMetadata
from legal_format_engine.renderers.docx_renderer import render_docx
from legal_format_engine.renderers.markdown_renderer import render_markdown
from legal_format_engine.rules.loader import load_ruleset

_letterhead_mgr = LetterheadManager()
_pattern_store = PatternStore()

app = FastAPI(
    title="Legal Format Engine API",
    description="Rules-based legal document formatting engine for Wisconsin appellate briefs.",
    version="0.1.0",
)

# CORS for Word Add-in and web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://localhost:8443",
        "https://localhost:3000",
        "null",  # Office Add-in sideloaded
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve Word Add-in static files (taskpane.html, .css, .js)
# Looks for word-addin/src/ relative to the project root
_addin_dir = Path(__file__).resolve().parent.parent.parent.parent / "word-addin" / "src"
if _addin_dir.is_dir():
    app.mount("/addin", StaticFiles(directory=str(_addin_dir), html=True), name="addin")


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


def _resolve_letterhead(letterhead_id: str | None) -> Letterhead | None:
    """Load a letterhead by ID, or return None."""
    if not letterhead_id:
        return None
    lh = _letterhead_mgr.get(letterhead_id)
    if not lh:
        raise HTTPException(status_code=404, detail=f"Letterhead '{letterhead_id}' not found")
    return lh


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

    letterhead = _resolve_letterhead(req.letterhead_id)

    doc = format_document(
        req.text, req.metadata, ruleset,
        word_count=req.word_count,
        insert_missing=req.insert_missing,
    )

    if req.output_format == "docx":
        output = Path(tempfile.mktemp(suffix=".docx"))
        path = render_docx(doc, ruleset, str(output), letterhead=letterhead)
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
    letterhead_id: str | None = Form(None),
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

    letterhead = _resolve_letterhead(letterhead_id)

    doc = format_document(
        text, meta, ruleset,
        word_count=word_count,
        insert_missing=insert_missing,
    )

    if output_format == "docx":
        output = Path(tempfile.mktemp(suffix=".docx"))
        path = render_docx(doc, ruleset, str(output), letterhead=letterhead)
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


# ── Letterheads ───────────────────────────────────────────────────────


def _lh_to_response(lh: Letterhead) -> LetterheadResponse:
    return LetterheadResponse(
        id=lh.id,
        name=lh.name,
        lines=[
            {"text": l.text, "bold": l.bold, "italic": l.italic,
             "font_size_pt": l.font_size_pt, "alignment": l.alignment}
            for l in lh.lines
        ],
        logo_path=lh.logo_path,
        logo_width_inches=lh.logo_width_inches,
        separator_line=lh.separator_line,
        spacing_after_pt=lh.spacing_after_pt,
    )


@app.get("/api/letterheads", response_model=LetterheadListResponse)
async def list_letterheads():
    """List all saved letterhead profiles."""
    return LetterheadListResponse(
        letterheads=[_lh_to_response(lh) for lh in _letterhead_mgr.list()]
    )


@app.get("/api/letterheads/{letterhead_id}", response_model=LetterheadResponse)
async def get_letterhead(letterhead_id: str):
    """Get a specific letterhead by ID."""
    lh = _letterhead_mgr.get(letterhead_id)
    if not lh:
        raise HTTPException(status_code=404, detail="Letterhead not found")
    return _lh_to_response(lh)


@app.post("/api/letterheads", response_model=LetterheadResponse, status_code=201)
async def create_letterhead(req: LetterheadCreate):
    """Create a new letterhead profile."""
    lh = Letterhead(
        name=req.name,
        lines=[
            LetterheadLine(
                text=l.text, bold=l.bold, italic=l.italic,
                font_size_pt=l.font_size_pt, alignment=l.alignment,
            )
            for l in req.lines
        ],
        logo_width_inches=req.logo_width_inches,
        separator_line=req.separator_line,
        spacing_after_pt=req.spacing_after_pt,
    )
    saved = _letterhead_mgr.save(lh)
    return _lh_to_response(saved)


@app.put("/api/letterheads/{letterhead_id}", response_model=LetterheadResponse)
async def update_letterhead(letterhead_id: str, req: LetterheadCreate):
    """Update an existing letterhead profile."""
    existing = _letterhead_mgr.get(letterhead_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Letterhead not found")

    existing.name = req.name
    existing.lines = [
        LetterheadLine(
            text=l.text, bold=l.bold, italic=l.italic,
            font_size_pt=l.font_size_pt, alignment=l.alignment,
        )
        for l in req.lines
    ]
    existing.logo_width_inches = req.logo_width_inches
    existing.separator_line = req.separator_line
    existing.spacing_after_pt = req.spacing_after_pt

    saved = _letterhead_mgr.save(existing)
    return _lh_to_response(saved)


@app.delete("/api/letterheads/{letterhead_id}")
async def delete_letterhead(letterhead_id: str):
    """Delete a letterhead profile."""
    if not _letterhead_mgr.delete(letterhead_id):
        raise HTTPException(status_code=404, detail="Letterhead not found")
    return {"deleted": True}


@app.post("/api/letterheads/{letterhead_id}/logo")
async def upload_letterhead_logo(letterhead_id: str, file: UploadFile = File(...)):
    """Upload a logo image for an existing letterhead."""
    lh = _letterhead_mgr.get(letterhead_id)
    if not lh:
        raise HTTPException(status_code=404, detail="Letterhead not found")

    suffix = Path(file.filename or "logo.png").suffix.lower()
    if suffix not in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
        raise HTTPException(status_code=422, detail="Logo must be an image file")

    tmp = Path(tempfile.mktemp(suffix=suffix))
    tmp.write_bytes(file.file.read())
    saved = _letterhead_mgr.save(lh, logo_source=tmp)
    tmp.unlink(missing_ok=True)

    return _lh_to_response(saved)


# ── Brief Analysis / Pattern Learning ───────────────────────────────


def _analysis_to_response(analysis) -> BriefUploadResponse:
    """Convert a BriefAnalysis to the API response schema."""
    return BriefUploadResponse(
        id=analysis.id,
        source_filename=analysis.source_filename,
        jurisdiction=analysis.jurisdiction,
        court_level=analysis.court_level,
        analyzed_at=analysis.analyzed_at,
        font_patterns=[fp.model_dump() for fp in analysis.font_patterns],
        margin_pattern=analysis.margin_pattern.model_dump() if analysis.margin_pattern else None,
        line_spacing=analysis.line_spacing,
        heading_patterns=[hp.model_dump() for hp in analysis.heading_patterns],
        section_patterns=[sp.model_dump() for sp in analysis.section_patterns],
        paragraph_indent_inches=analysis.paragraph_indent_inches,
        block_quote_indent_inches=analysis.block_quote_indent_inches,
    )


@app.post("/api/briefs/upload", response_model=BriefUploadResponse, status_code=201)
async def upload_brief(
    file: UploadFile = File(...),
    jurisdiction: str | None = Form(None),
    court_level: str | None = Form(None),
):
    """Upload a brief (DOCX or PDF) for formatting analysis.

    Extracts formatting patterns from the uploaded document and stores
    them for learning. Optionally tag with jurisdiction and court level.
    """
    filename = file.filename or "unknown"
    suffix = Path(filename).suffix.lower()
    if suffix not in (".docx", ".pdf"):
        raise HTTPException(
            status_code=422,
            detail="Unsupported file type. Upload a .docx or .pdf file.",
        )

    # Write to temp file for analysis
    tmp = Path(tempfile.mktemp(suffix=suffix))
    try:
        content = file.file.read()
        if not content:
            raise HTTPException(status_code=422, detail="Uploaded file is empty.")
        tmp.write_bytes(content)

        analysis = analyze_brief(tmp, jurisdiction=jurisdiction, court_level=court_level)
        # Override source filename with original upload name
        analysis.source_filename = filename
        _pattern_store.save(analysis)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze brief: {exc}",
        )
    finally:
        tmp.unlink(missing_ok=True)

    return _analysis_to_response(analysis)


@app.get("/api/briefs/patterns/{jurisdiction}", response_model=AggregatePatternResponse)
async def get_patterns(jurisdiction: str, court_level: str | None = None):
    """Get aggregated learned patterns for a jurisdiction.

    Computes consensus formatting patterns (fonts, margins, headings,
    sections) from all briefs uploaded for the given jurisdiction.
    """
    agg = _pattern_store.aggregate(jurisdiction, court_level=court_level)
    return AggregatePatternResponse(
        jurisdiction=agg.jurisdiction,
        court_level=agg.court_level,
        brief_count=agg.brief_count,
        font=agg.font.model_dump() if agg.font else None,
        margins=agg.margins.model_dump() if agg.margins else None,
        line_spacing=agg.line_spacing,
        headings=[h.model_dump() for h in agg.headings],
        sections=[s.model_dump() for s in agg.sections],
        paragraph_indent_inches=agg.paragraph_indent_inches,
    )


@app.get("/api/briefs/analyses", response_model=BriefAnalysisListResponse)
async def list_analyses():
    """List all uploaded brief analyses."""
    analyses = _pattern_store.list_all()
    return BriefAnalysisListResponse(
        analyses=[_analysis_to_response(a) for a in analyses],
        total=len(analyses),
    )


@app.delete("/api/briefs/analyses/{analysis_id}")
async def delete_analysis(analysis_id: str):
    """Delete a specific brief analysis by ID."""
    if not _pattern_store.delete(analysis_id):
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"deleted": True}


# ── Google Docs Upload ─────────────────────────────────────────────────


@app.post("/api/documents/upload-gdoc", response_model=GoogleDocUploadResponse, status_code=201)
async def upload_google_doc(
    url: str = Form(...),
    jurisdiction: str | None = Form(None),
    court_level: str | None = Form(None),
    document_type: str | None = Form(None),
    tags: str | None = Form(None),
    notes: str | None = Form(None),
):
    """Upload a Google Doc by its share URL.

    Downloads the document as DOCX via the Google Docs export URL and
    runs the standard brief analysis pipeline on it.  Only works for
    documents shared publicly (anyone with the link).
    """
    # Validate URL
    if not GoogleDocsConnector.is_google_docs_url(url):
        raise HTTPException(
            status_code=422,
            detail="Not a valid Google Docs URL. Expected a URL like "
                   "https://docs.google.com/document/d/{DOC_ID}/edit",
        )

    # Download as DOCX
    tmp_path: Path | None = None
    try:
        tmp_path = GoogleDocsConnector.download_as_docx(url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download Google Doc: {exc}",
        )

    # Analyze with the standard brief analyzer
    try:
        analysis = analyze_brief(
            tmp_path,
            jurisdiction=jurisdiction,
            court_level=court_level,
        )
        doc_id = GoogleDocsConnector.extract_doc_id(url)
        analysis.source_filename = f"gdoc-{doc_id}.docx"
        _pattern_store.save(analysis)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze Google Doc: {exc}",
        )
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)

    return GoogleDocUploadResponse(
        id=analysis.id,
        source_filename=analysis.source_filename,
        source_url=url,
        jurisdiction=analysis.jurisdiction,
        court_level=analysis.court_level,
        document_type=document_type,
        analyzed_at=analysis.analyzed_at,
        font_patterns=[fp.model_dump() for fp in analysis.font_patterns],
        margin_pattern=analysis.margin_pattern.model_dump() if analysis.margin_pattern else None,
        line_spacing=analysis.line_spacing,
        heading_patterns=[hp.model_dump() for hp in analysis.heading_patterns],
        section_patterns=[sp.model_dump() for sp in analysis.section_patterns],
        paragraph_indent_inches=analysis.paragraph_indent_inches,
        block_quote_indent_inches=analysis.block_quote_indent_inches,
        tags=tags,
        notes=notes,
    )
