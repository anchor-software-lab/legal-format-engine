"""Pipeline orchestrator - ties all engines together."""

from __future__ import annotations
from typing import Optional

from legal_format_engine.models.document import (
    Attorney,
    CaseMetadata,
    ContentBlock,
    DocumentMetadata,
    DocumentModel,
    Section,
)
from legal_format_engine.models.section import Ruleset
from legal_format_engine.engines.caption_engine import generate_caption
from legal_format_engine.engines.heading_engine import normalize_headings
from legal_format_engine.engines.section_engine import (
    ValidationIssue,
    insert_missing_sections,
    reorder_sections,
    validate_sections,
)
from legal_format_engine.engines.boilerplate_engine import (
    generate_certifications,
    generate_signature_block,
)
from legal_format_engine.parsers.plain_text_parser import parse_plain_text
from legal_format_engine.renderers.docx_renderer import render_docx
from legal_format_engine.renderers.markdown_renderer import render_markdown
from legal_format_engine.rules.base import load_ruleset


def format_document(
    text: str,
    case_meta: Optional[CaseMetadata] = None,
    doc_meta: Optional[DocumentMetadata] = None,
    attorney: Optional[Attorney] = None,
    word_count: Optional[int] = None,
    insert_missing: bool = True,
) -> DocumentModel:
    """Full formatting pipeline: parse, validate, reorder, normalize, generate boilerplate.

    Returns a fully formatted DocumentModel.
    """
    if doc_meta is None:
        doc_meta = DocumentMetadata()

    # Load ruleset
    ruleset = load_ruleset(
        jurisdiction=doc_meta.jurisdiction,
        document_type=doc_meta.document_type,
        variant=doc_meta.variant,
    )

    # Parse
    doc = parse_plain_text(text, doc_meta)

    # Validate and reorder
    if insert_missing:
        doc.sections = insert_missing_sections(doc.sections, ruleset)
    doc.sections = reorder_sections(doc.sections, ruleset)

    # Normalize headings
    doc.sections = normalize_headings(doc.sections, ruleset)

    # Generate caption
    if case_meta:
        doc_title = doc_meta.document_title or "Brief"
        doc.caption = generate_caption(case_meta, doc_title, ruleset)
        doc.case_metadata = case_meta

    # Generate boilerplate
    if attorney:
        doc.signature_block = generate_signature_block(attorney)
        doc.certifications = generate_certifications(ruleset, attorney, word_count)

    return doc


def format_and_render_markdown(
    text: str,
    case_meta: Optional[CaseMetadata] = None,
    doc_meta: Optional[DocumentMetadata] = None,
    attorney: Optional[Attorney] = None,
    word_count: Optional[int] = None,
) -> str:
    """Format a document and render as Markdown."""
    doc = format_document(text, case_meta, doc_meta, attorney, word_count)
    return render_markdown(doc)


def format_and_render_docx(
    text: str,
    case_meta: Optional[CaseMetadata] = None,
    doc_meta: Optional[DocumentMetadata] = None,
    attorney: Optional[Attorney] = None,
    word_count: Optional[int] = None,
    output_path: Optional[str] = None,
    letterhead_lines: Optional[list[dict]] = None,
) -> bytes:
    """Format a document and render as DOCX bytes."""
    doc_meta = doc_meta or DocumentMetadata()
    ruleset = load_ruleset(
        jurisdiction=doc_meta.jurisdiction,
        document_type=doc_meta.document_type,
        variant=doc_meta.variant,
    )
    doc = format_document(text, case_meta, doc_meta, attorney, word_count)
    return render_docx(doc, ruleset, output_path, letterhead_lines)


def validate_document(
    text: str,
    doc_meta: Optional[DocumentMetadata] = None,
) -> list[ValidationIssue]:
    """Parse and validate a document against its ruleset."""
    doc_meta = doc_meta or DocumentMetadata()
    ruleset = load_ruleset(
        jurisdiction=doc_meta.jurisdiction,
        document_type=doc_meta.document_type,
        variant=doc_meta.variant,
    )
    doc = parse_plain_text(text, doc_meta)
    return validate_sections(doc.sections, ruleset)
