"""Classify a paragraph's `SegmentKind` from its style and indent.

A "segment" in the quality-gate vocabulary is a logical unit that
checkers reason about — a heading vs a body paragraph vs a block quote.
We classify from python-docx's `paragraph.style.name` plus a couple of
heuristics for block quotes (which are rarely styled explicitly).
"""

from __future__ import annotations

from typing import Any

from legal_quality_gate.types import ObservedStyle, SegmentKind

# Block-quote heuristics. Lawyers often format block quotes as paragraphs
# indented ~0.5"-1" on both margins; we treat a left-indent ≥ this
# threshold as a block quote when no explicit style says otherwise.
_BLOCK_QUOTE_INDENT_INCHES = 0.5


def classify_segment_kind(
    paragraph: Any, style: ObservedStyle | None = None
) -> SegmentKind:
    style_name = (paragraph.style.name or "").lower() if paragraph.style else ""

    if style_name.startswith("heading") or style_name == "title":
        return SegmentKind.HEADING

    if style_name in {"quote", "blocktext", "block text", "intense quote"}:
        return SegmentKind.BLOCK_QUOTE

    # Heuristic block quote: a paragraph with substantial left indent and
    # no first-line indent is almost certainly a block quote in legal
    # briefs.
    paragraph_format = paragraph.paragraph_format
    left_indent = _inches(paragraph_format.left_indent)
    first_line_indent = _inches(paragraph_format.first_line_indent)
    if (
        left_indent is not None
        and left_indent >= _BLOCK_QUOTE_INDENT_INCHES
        and (first_line_indent is None or abs(first_line_indent) < 1e-6)
    ):
        return SegmentKind.BLOCK_QUOTE

    return SegmentKind.PARAGRAPH


def _inches(measurement: Any) -> float | None:
    if measurement is None:
        return None
    try:
        return float(measurement.inches)
    except AttributeError:
        return None


class Segmenter:
    """Thin wrapper exposing `classify_segment_kind` as an object.

    Kept as a class so the public API has room to grow (e.g. a stateful
    segmenter that tracks numbering context across paragraphs).
    """

    def classify(self, paragraph: Any, style: ObservedStyle | None = None) -> SegmentKind:
        return classify_segment_kind(paragraph, style)
