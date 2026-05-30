"""Tests for `legal_docx.parse_docx`."""

from __future__ import annotations

from legal_docx import parse_docx
from legal_quality_gate.types import SegmentKind


def test_parse_produces_document_with_expected_segments(sample_brief_docx):
    result = parse_docx(sample_brief_docx)
    document = result.document

    assert document.source_uri == str(sample_brief_docx)
    assert len(document.sha256) == 64
    assert len(document.segments) == 4

    # Ordinals are sequential, ids are deterministic.
    assert [s.ordinal for s in document.segments] == [0, 1, 2, 3]
    assert [s.id for s in document.segments] == [
        "seg-00000",
        "seg-00001",
        "seg-00002",
        "seg-00003",
    ]


def test_segment_kinds_classified(sample_brief_docx):
    result = parse_docx(sample_brief_docx)
    kinds = [s.kind for s in result.document.segments]
    assert kinds == [
        SegmentKind.HEADING,
        SegmentKind.PARAGRAPH,
        SegmentKind.BLOCK_QUOTE,
        SegmentKind.PARAGRAPH,
    ]


def test_observed_style_extracted_from_runs(sample_brief_docx):
    result = parse_docx(sample_brief_docx)
    body, quote, concl = result.document.segments[1:4]

    # Body paragraph: 12pt Times New Roman, double-spaced, 0.5" first-line
    # indent.
    assert body.style_observed.font_name == "Times New Roman"
    assert body.style_observed.font_size_pt == 12.0
    assert body.style_observed.line_spacing == 2.0
    assert body.style_observed.indent_inches == 0.5

    # Block quote: 13pt, single-spaced.
    assert quote.style_observed.font_size_pt == 13.0
    assert quote.style_observed.line_spacing == 1.0

    # Conclusion: 13pt, double-spaced.
    assert concl.style_observed.font_size_pt == 13.0
    assert concl.style_observed.line_spacing == 2.0


def test_section_margins_applied_to_every_segment(sample_brief_docx):
    result = parse_docx(sample_brief_docx)
    for segment in result.document.segments:
        assert segment.style_observed.margin_top_inches == 1.0
        assert segment.style_observed.margin_bottom_inches == 1.0
        assert segment.style_observed.margin_left_inches == 1.0
        assert segment.style_observed.margin_right_inches == 1.0


def test_text_loader_returns_plaintext_per_segment(sample_brief_docx):
    result = parse_docx(sample_brief_docx)
    body = result.document.segments[1]
    text = result.text_loader(body)
    assert text.startswith("This Court reviews")
    assert len(text) == body.char_length


def test_segment_text_hash_matches_text(sample_brief_docx):
    import hashlib

    result = parse_docx(sample_brief_docx)
    for segment in result.document.segments:
        text = result.text_by_segment_id[segment.id]
        expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
        assert segment.text_hash == expected


def test_document_id_can_be_overridden(sample_brief_docx):
    result = parse_docx(sample_brief_docx, document_id="explicit-id")
    assert result.document.id == "explicit-id"
