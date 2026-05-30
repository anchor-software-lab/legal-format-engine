"""DOCX parsing, segmentation, and annotated-writer.

Public entry points:

- `parse_docx(path) -> ParseResult` — open a .docx and produce a
  `legal_quality_gate.Document` plus a `text_loader` that retrieves
  per-segment plaintext. The `Document` itself only carries hashes and
  observed style, keeping plaintext out of metadata that may end up in
  encrypted-only storage.
- `Segmenter` — classifies paragraphs into `SegmentKind`.

The annotated writer (round-tripping findings back into the docx as
tracked changes + comments) lands in the next iteration of v0.
"""

from legal_docx.annotated_writer import write_annotated
from legal_docx.parser import ParseResult, parse_docx
from legal_docx.segmenter import Segmenter, classify_segment_kind

__all__ = [
    "ParseResult",
    "Segmenter",
    "classify_segment_kind",
    "parse_docx",
    "write_annotated",
]
