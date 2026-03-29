"""Document formatting pipeline.

Orchestrates the full formatting flow: parse -> validate -> normalize -> generate -> render.
"""

from __future__ import annotations

from pathlib import Path

from legal_format_engine.engines.boilerplate_engine import (
    generate_certifications,
    generate_signature_block,
)
from legal_format_engine.engines.caption_engine import generate_caption
from legal_format_engine.engines.heading_engine import normalize_headings
from legal_format_engine.engines.section_engine import (
    insert_missing_sections,
    reorder_sections,
    validate_sections,
)
from legal_format_engine.models.document import LegalDocument
from legal_format_engine.models.metadata import DocumentMetadata
from legal_format_engine.parsers.plain_text_parser import parse_plain_text
from legal_format_engine.renderers.docx_renderer import render_docx
from legal_format_engine.renderers.markdown_renderer import render_markdown
from legal_format_engine.rules.schema import Ruleset


def format_document(
    text: str,
    metadata: DocumentMetadata,
    ruleset: Ruleset,
    word_count: int | None = None,
    service_parties: str | None = None,
    insert_missing: bool = True,
) -> LegalDocument:
    """Run the full formatting pipeline on raw text.

    Steps:
    1. Parse input text into sections
    2. Generate caption from metadata
    3. Validate sections against ruleset
    4. Reorder sections to canonical order
    5. Insert stubs for missing required sections (optional)
    6. Normalize headings
    7. Generate signature block and certifications

    Args:
        text: Raw document text.
        metadata: Case and document metadata.
        ruleset: The active formatting ruleset.
        word_count: Optional word count for compliance cert.
        service_parties: Optional formatted party list for service cert.
        insert_missing: Whether to insert stubs for missing sections.

    Returns:
        A fully formatted LegalDocument ready for rendering.
    """
    # Step 1: Parse
    doc = parse_plain_text(text)

    # Step 2: Caption
    doc.caption = generate_caption(metadata, ruleset.caption_rule)

    # Step 3: Validate
    doc = validate_sections(doc, ruleset)

    # Step 4: Reorder
    doc = reorder_sections(doc, ruleset)

    # Step 5: Insert missing stubs
    if insert_missing:
        doc = insert_missing_sections(doc, ruleset)

    # Step 6: Normalize headings
    doc.sections = normalize_headings(doc.sections, ruleset)

    # Step 7: Boilerplate
    doc.signature_block = generate_signature_block(metadata)
    doc.certifications = generate_certifications(
        metadata, ruleset.certifications, word_count, service_parties
    )

    # Attach metadata reference
    doc.metadata = metadata.model_dump()

    return doc


def format_and_render_docx(
    text: str,
    metadata: DocumentMetadata,
    ruleset: Ruleset,
    output_path: str | Path,
    word_count: int | None = None,
    service_parties: str | None = None,
) -> tuple[LegalDocument, Path]:
    """Full pipeline: parse, format, and render to DOCX.

    Returns:
        Tuple of (formatted LegalDocument, output file Path).
    """
    doc = format_document(text, metadata, ruleset, word_count, service_parties)
    path = render_docx(doc, ruleset, output_path)
    return doc, path


def format_and_render_markdown(
    text: str,
    metadata: DocumentMetadata,
    ruleset: Ruleset,
    word_count: int | None = None,
    service_parties: str | None = None,
) -> tuple[LegalDocument, str]:
    """Full pipeline: parse, format, and render to Markdown.

    Returns:
        Tuple of (formatted LegalDocument, markdown string).
    """
    doc = format_document(text, metadata, ruleset, word_count, service_parties)
    md = render_markdown(doc)
    return doc, md
