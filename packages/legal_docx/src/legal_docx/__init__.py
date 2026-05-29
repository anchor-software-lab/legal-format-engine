"""DOCX parsing, segmentation, and annotated-writer.

v0 surface (planned):
- `parser.parse_docx(path) -> Document` (legal_quality_gate.Document)
- `segmenter.Segmenter` — produce Segment list with ObservedStyle
- `annotated_writer.write_annotated(doc, findings, out_path)` — emit a
  docx with tracked changes + Word comments anchored to finding ranges
"""
