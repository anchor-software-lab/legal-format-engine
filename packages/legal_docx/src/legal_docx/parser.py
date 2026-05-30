"""Parse a .docx into a `legal_quality_gate.Document`.

The parser produces a `ParseResult` containing:
  - `document`: the metadata-only `Document` (segments, hashes, observed
    style, citation spans — no plaintext).
  - `text_by_segment_id`: a side dict of plaintext, keyed by segment id.
  - `text_loader`: a callable suitable for `CheckContext(text_loader=…)`.

The plaintext side dict is intentionally separate so callers can
either (a) hold it in memory for local CLI runs, or (b) write it into
the encrypted blob store for SaaS runs without ever putting it on the
`Document` itself.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from docx import Document as load_docx_document

from legal_docx._style import observed_style_for_paragraph, section_margins
from legal_docx.segmenter import classify_segment_kind
from legal_quality_gate.types import Document, Segment


@dataclass
class ParseResult:
    document: Document
    text_by_segment_id: dict[str, str] = field(default_factory=dict)

    @property
    def text_loader(self) -> Callable[[Segment], str]:
        return lambda segment: self.text_by_segment_id.get(segment.id, "")

    @property
    def segment_ordinal_by_id(self) -> dict[str, int]:
        """Map from segment id back to docx paragraph index.

        Needed by `legal_docx.write_annotated` to locate the paragraph
        a Suggestion targets when applying REFORMAT fixes.
        """
        return {seg.id: seg.ordinal for seg in self.document.segments}


def parse_docx(path: str | Path, *, document_id: str | None = None) -> ParseResult:
    """Parse a .docx file into a `Document` plus a plaintext side-table.

    `document_id` is optional; if not provided, one is generated.
    """
    path = Path(path)
    docx_document = load_docx_document(str(path))

    # Section margins. Most briefs have one section; we apply the first
    # section's margins to every segment for now. A multi-section parser
    # comes in v1 alongside running headers/footers handling.
    section = (
        docx_document.sections[0] if docx_document.sections else None
    )
    margins = section_margins(section) if section is not None else {
        "top": None, "bottom": None, "left": None, "right": None,
    }

    segments: list[Segment] = []
    text_by_segment_id: dict[str, str] = {}

    for ordinal, paragraph in enumerate(docx_document.paragraphs):
        text = paragraph.text
        if not text and not paragraph.runs:
            # Skip truly empty paragraphs (no runs, no text). Keep
            # whitespace-only paragraphs because they affect layout.
            continue

        observed = observed_style_for_paragraph(paragraph, margins)
        kind = classify_segment_kind(paragraph, observed)
        segment_id = f"seg-{ordinal:05d}"

        segments.append(
            Segment(
                id=segment_id,
                kind=kind,
                ordinal=ordinal,
                text_hash=_sha256(text),
                char_length=len(text),
                style_observed=observed,
            )
        )
        text_by_segment_id[segment_id] = text

    document = Document(
        id=document_id or str(uuid.uuid4()),
        source_uri=str(path),
        sha256=_sha256_file(path),
        segments=segments,
    )

    return ParseResult(document=document, text_by_segment_id=text_by_segment_id)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
