"""FastAPI server - REST API for the legal format engine."""

from __future__ import annotations
import base64
import io
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from legal_format_engine.models.document import (
    Attorney,
    CaseMetadata,
    DocumentMetadata,
    Party,
    PartyRole,
)
from legal_format_engine.models.section import Ruleset
from legal_format_engine.pipeline import (
    format_document,
    validate_document,
)
from legal_format_engine.renderers.docx_renderer import render_docx
from legal_format_engine.renderers.markdown_renderer import render_markdown
from legal_format_engine.engines.citation_engine import check_citations
from legal_format_engine.rules.base import load_ruleset, list_rulesets
from legal_format_engine.letterhead.manager import LetterheadManager
from legal_format_engine.letterhead.models import Letterhead, LetterheadLine

app = FastAPI(title="Legal Format Engine", version="0.1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://localhost:8443", "https://127.0.0.1:8443", "null"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for the Word Add-in
ADDIN_DIR = Path(__file__).parent.parent.parent.parent / "word-addin"
if ADDIN_DIR.exists():
    app.mount("/addin", StaticFiles(directory=str(ADDIN_DIR), html=True), name="addin")

# Letterhead manager
_letterhead_mgr = LetterheadManager()

# ML pipeline (lazy init)
_ml_pipeline = None


def _get_ml_pipeline():
    global _ml_pipeline
    if _ml_pipeline is None:
        from legal_format_engine.ml.pipeline import MLPipeline
        _ml_pipeline = MLPipeline()
    return _ml_pipeline


# ─── Request/Response Models ───


class PartyRequest(BaseModel):
    name: str
    role: str = "defendant"
    designation: Optional[str] = None


class AttorneyRequest(BaseModel):
    name: str = ""
    bar_number: Optional[str] = None
    firm: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class FormatRequest(BaseModel):
    text: str
    jurisdiction: str = "wisconsin"
    court_level: str = "court_of_appeals"
    document_type: str = "appellate_brief"
    document_title: Optional[str] = None
    variant: Optional[str] = None
    case_name: Optional[str] = None
    case_number: Optional[str] = None
    district: Optional[str] = None
    county: Optional[str] = None
    judge: Optional[str] = None
    parties: list[PartyRequest] = Field(default_factory=list)
    attorney: Optional[AttorneyRequest] = None
    word_count: Optional[int] = None
    insert_missing: bool = True
    output_format: str = "docx"
    letterhead_id: Optional[str] = None


class ValidateRequest(BaseModel):
    text: str
    jurisdiction: str = "wisconsin"
    document_type: str = "appellate_brief"
    variant: Optional[str] = None


class CitationRequest(BaseModel):
    text: str


class LetterheadLineRequest(BaseModel):
    text: str
    bold: bool = False
    italic: bool = False
    font_size_pt: float = 10.0
    alignment: str = "left"


class LetterheadRequest(BaseModel):
    name: str
    lines: list[LetterheadLineRequest] = Field(default_factory=list)


# ─── Health ───


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


# ─── Format ───


@app.post("/api/format")
def api_format(req: FormatRequest):
    """Format a document and return DOCX or markdown."""
    doc_meta = DocumentMetadata(
        jurisdiction=req.jurisdiction,
        court_level=req.court_level,
        document_type=req.document_type,
        document_title=req.document_title,
        variant=req.variant,
    )

    case_meta = None
    if req.case_name or req.case_number:
        parties = [
            Party(
                name=p.name,
                role=PartyRole(p.role),
                designation=p.designation,
            )
            for p in req.parties
        ]
        case_meta = CaseMetadata(
            case_name=req.case_name or "",
            case_number=req.case_number or "",
            district=req.district,
            county=req.county,
            judge=req.judge,
            parties=parties,
        )

    attorney = None
    if req.attorney and req.attorney.name:
        attorney = Attorney(**req.attorney.model_dump())

    doc = format_document(
        text=req.text,
        case_meta=case_meta,
        doc_meta=doc_meta,
        attorney=attorney,
        word_count=req.word_count,
        insert_missing=req.insert_missing,
    )

    # Resolve letterhead
    letterhead_lines = None
    if req.letterhead_id:
        lh = _letterhead_mgr.get(req.letterhead_id)
        if lh:
            letterhead_lines = _letterhead_mgr.to_render_lines(lh)

    if req.output_format == "markdown":
        md = render_markdown(doc)
        return {"markdown": md}

    # DOCX
    ruleset = load_ruleset(req.jurisdiction, req.document_type, req.variant)
    docx_bytes = render_docx(doc, ruleset, letterhead_lines=letterhead_lines)
    encoded = base64.b64encode(docx_bytes).decode()
    return {"docx_base64": encoded, "size_bytes": len(docx_bytes)}


# ─── Format Upload ───


@app.post("/api/format/upload")
async def api_format_upload(
    file: UploadFile = File(...),
    jurisdiction: str = Form("wisconsin"),
    document_type: str = Form("appellate_brief"),
    variant: Optional[str] = Form(None),
    output_format: str = Form("docx"),
    letterhead_id: Optional[str] = Form(None),
):
    """Format an uploaded document file."""
    content = await file.read()
    filename = file.filename or ""

    if filename.endswith(".docx"):
        from legal_format_engine.parsers.docx_parser import parse_docx_bytes
        doc_meta = DocumentMetadata(jurisdiction=jurisdiction, document_type=document_type, variant=variant)
        doc = parse_docx_bytes(content, doc_meta)
    elif filename.endswith(".pdf"):
        from legal_format_engine.parsers.pdf_parser import parse_pdf_bytes
        doc_meta = DocumentMetadata(jurisdiction=jurisdiction, document_type=document_type, variant=variant)
        doc = parse_pdf_bytes(content, doc_meta)
    else:
        text = content.decode("utf-8", errors="replace")
        doc_meta = DocumentMetadata(jurisdiction=jurisdiction, document_type=document_type, variant=variant)
        from legal_format_engine.parsers.plain_text_parser import parse_plain_text
        doc = parse_plain_text(text, doc_meta)

    letterhead_lines = None
    if letterhead_id:
        lh = _letterhead_mgr.get(letterhead_id)
        if lh:
            letterhead_lines = _letterhead_mgr.to_render_lines(lh)

    if output_format == "markdown":
        md = render_markdown(doc)
        return {"markdown": md}

    ruleset = load_ruleset(jurisdiction, document_type, variant)
    docx_bytes = render_docx(doc, ruleset, letterhead_lines=letterhead_lines)
    encoded = base64.b64encode(docx_bytes).decode()
    return {"docx_base64": encoded, "size_bytes": len(docx_bytes)}


# ─── Validate ───


@app.post("/api/validate")
def api_validate(req: ValidateRequest):
    issues = validate_document(
        req.text,
        DocumentMetadata(
            jurisdiction=req.jurisdiction,
            document_type=req.document_type,
            variant=req.variant,
        ),
    )
    return {
        "issues": [i.to_dict() for i in issues],
        "count": len(issues),
    }


@app.post("/api/validate/upload")
async def api_validate_upload(
    file: UploadFile = File(...),
    jurisdiction: str = Form("wisconsin"),
    document_type: str = Form("appellate_brief"),
):
    content = await file.read()
    text = content.decode("utf-8", errors="replace")
    issues = validate_document(
        text,
        DocumentMetadata(jurisdiction=jurisdiction, document_type=document_type),
    )
    return {"issues": [i.to_dict() for i in issues], "count": len(issues)}


# ─── Citations ───


@app.post("/api/citations")
def api_citations(req: CitationRequest):
    report = check_citations(req.text)
    return {
        "stats": report.stats,
        "issues": [i.to_dict() for i in report.issues],
        "citation_count": report.stats.get("total", 0),
    }


@app.post("/api/citations/upload")
async def api_citations_upload(file: UploadFile = File(...)):
    content = await file.read()
    text = content.decode("utf-8", errors="replace")
    report = check_citations(text)
    return {
        "stats": report.stats,
        "issues": [i.to_dict() for i in report.issues],
        "citation_count": report.stats.get("total", 0),
    }


# ─── Rulesets ───


@app.get("/api/rulesets")
def api_list_rulesets():
    return {"rulesets": list_rulesets()}


# ─── Letterheads ───


@app.post("/api/letterheads")
def api_create_letterhead(req: LetterheadRequest):
    lines = [LetterheadLine(**l.model_dump()) for l in req.lines]
    lh = Letterhead(name=req.name, lines=lines)
    saved = _letterhead_mgr.save(lh)
    return saved.model_dump()


@app.get("/api/letterheads")
def api_list_letterheads():
    return [lh.model_dump() for lh in _letterhead_mgr.list_all()]


@app.get("/api/letterheads/{letterhead_id}")
def api_get_letterhead(letterhead_id: str):
    lh = _letterhead_mgr.get(letterhead_id)
    if not lh:
        raise HTTPException(status_code=404, detail="Letterhead not found")
    return lh.model_dump()


@app.delete("/api/letterheads/{letterhead_id}")
def api_delete_letterhead(letterhead_id: str):
    if _letterhead_mgr.delete(letterhead_id):
        return {"deleted": True}
    raise HTTPException(status_code=404, detail="Letterhead not found")


# ─── ML Pipeline ───


@app.post("/api/ml/ingest")
async def api_ml_ingest(
    file: UploadFile = File(...),
    jurisdiction: Optional[str] = Form(None),
    court_level: Optional[str] = Form(None),
    document_type: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    firm: Optional[str] = Form(None),
):
    """Ingest a document for ML processing."""
    pipeline = _get_ml_pipeline()
    content = await file.read()
    filename = file.filename or "unknown"

    result = pipeline.ingest(
        data=content,
        filename=filename,
        jurisdiction=jurisdiction,
        court_level=court_level,
        document_type=document_type,
        author=author,
        firm=firm,
    )
    return result


@app.post("/api/ml/ingest-batch")
async def api_ml_ingest_batch(
    files: list[UploadFile] = File(...),
    jurisdiction: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    firm: Optional[str] = Form(None),
):
    """Ingest multiple documents."""
    pipeline = _get_ml_pipeline()
    results = []
    for f in files:
        content = await f.read()
        r = pipeline.ingest(
            data=content,
            filename=f.filename or "unknown",
            jurisdiction=jurisdiction,
            author=author,
            firm=firm,
        )
        results.append(r)
    return {"results": results, "count": len(results)}


@app.post("/api/ml/ingest-archive")
async def api_ml_ingest_archive(
    file: UploadFile = File(...),
    jurisdiction: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    firm: Optional[str] = Form(None),
):
    """Ingest an archive (ZIP, RAR, Adobe Portfolio) of documents."""
    pipeline = _get_ml_pipeline()
    content = await file.read()
    filename = file.filename or "archive"

    results = pipeline.ingest_archive(
        data=content,
        filename=filename,
        jurisdiction=jurisdiction,
        author=author,
        firm=firm,
    )
    return {"results": results, "count": len(results)}


@app.get("/api/ml/learn")
def api_ml_learn(jurisdiction: Optional[str] = None):
    """Run learner on stored documents."""
    pipeline = _get_ml_pipeline()
    patterns = pipeline.learn(jurisdiction=jurisdiction)
    return patterns


@app.get("/api/ml/suggest-ruleset")
def api_ml_suggest_ruleset(jurisdiction: str = "wisconsin"):
    """Generate a YAML ruleset from ML learned patterns."""
    pipeline = _get_ml_pipeline()
    yaml_text = pipeline.suggest_ruleset(jurisdiction)
    return {"yaml": yaml_text, "jurisdiction": jurisdiction}


@app.get("/api/ml/recommend")
def api_ml_recommend(jurisdiction: str = "wisconsin"):
    """Compare ML patterns against existing ruleset."""
    pipeline = _get_ml_pipeline()
    recommendations = pipeline.recommend(jurisdiction)
    return {"recommendations": recommendations, "jurisdiction": jurisdiction}


@app.get("/api/ml/documents")
def api_ml_documents():
    """List stored ML documents."""
    pipeline = _get_ml_pipeline()
    return pipeline.list_documents()


@app.get("/api/ml/stats")
def api_ml_stats():
    """Get ML document store statistics."""
    pipeline = _get_ml_pipeline()
    return pipeline.stats()


# ─── Style Profiles ───


@app.get("/api/ml/styles")
def api_ml_styles():
    """List learned style profiles."""
    pipeline = _get_ml_pipeline()
    return pipeline.list_styles()


@app.get("/api/ml/styles/{identifier}")
def api_ml_style(identifier: str):
    """Get a specific style profile by author or firm name."""
    pipeline = _get_ml_pipeline()
    style = pipeline.get_style(identifier)
    if not style:
        raise HTTPException(status_code=404, detail="Style not found")
    return style


@app.get("/api/ml/resolve-format")
def api_ml_resolve_format(
    jurisdiction: str = "wisconsin",
    document_type: str = "appellate_brief",
    author: Optional[str] = None,
    firm: Optional[str] = None,
):
    """Resolve final format by applying rule hierarchy:
    Court Rules > ML Patterns > Style Profiles > Defaults.
    """
    pipeline = _get_ml_pipeline()
    resolved = pipeline.resolve_format(
        jurisdiction=jurisdiction,
        document_type=document_type,
        author=author,
        firm=firm,
    )
    return resolved
