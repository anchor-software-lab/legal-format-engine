"""Round-trip the annotated writer: parse → run pipeline → apply fixes → re-parse.

Proves that the v0 fix path actually changes the document and that a
re-parse sees the corrected style.
"""

from __future__ import annotations

import asyncio

from legal_docx import parse_docx, write_annotated
from legal_format_engine import build_formatting_checker
from legal_quality_gate import (
    CheckContext,
    CheckerRegistry,
    Pipeline,
    Severity,
)


def test_round_trip_applies_safe_suggestions(sample_brief_docx, tmp_path):
    rules = {"page_format": {"font_size_pt": 13.0}}

    # First pass: find safe suggestions.
    first = parse_docx(sample_brief_docx)
    registry = CheckerRegistry()
    registry.register(build_formatting_checker(rules=rules))
    ctx = CheckContext(text_loader=first.text_loader)
    report = asyncio.run(Pipeline(registry).run(first.document, ctx))

    safe_suggestions = [
        f.suggestion
        for f in report.findings
        if f.suggestion is not None and f.suggestion.auto_apply_safe
    ]
    assert safe_suggestions, "fixture should produce at least one safe suggestion"

    # Apply suggestions to a new docx.
    fixed_path = tmp_path / "fixed.docx"
    write_annotated(
        original_path=sample_brief_docx,
        suggestions=safe_suggestions,
        out_path=fixed_path,
        segment_ordinal_by_id=first.segment_ordinal_by_id,
    )
    assert fixed_path.exists()

    # Re-parse and confirm the violations are gone.
    second = parse_docx(fixed_path)
    body_after = second.document.segments[1]
    assert body_after.style_observed.font_size_pt == 13.0

    registry2 = CheckerRegistry()
    registry2.register(build_formatting_checker(rules=rules))
    ctx2 = CheckContext(text_loader=second.text_loader)
    report2 = asyncio.run(Pipeline(registry2).run(second.document, ctx2))

    rule_findings = [
        f for f in report2.findings
        if f.rule_id == "FORMAT.FONT.SIZE" and f.severity is Severity.ERROR
    ]
    assert rule_findings == []


def test_writer_skips_unsupported_suggestion_kinds(sample_brief_docx, tmp_path):
    """REPLACE/INSERT/DELETE suggestions are silently ignored in v0."""
    from legal_quality_gate.types import CharRange, Suggestion, SuggestionKind

    result = parse_docx(sample_brief_docx)
    seg = result.document.segments[0]

    suggestions = [
        Suggestion(
            kind=SuggestionKind.REPLACE,
            range=CharRange(segment_id=seg.id, start=0, end=5),
            new_text="REPLACED",
            rationale="test",
        ),
        Suggestion(
            kind=SuggestionKind.INSERT,
            range=CharRange(segment_id=seg.id, start=0, end=0),
            new_text="INSERTED",
            rationale="test",
        ),
    ]
    fixed_path = tmp_path / "unchanged.docx"
    write_annotated(
        original_path=sample_brief_docx,
        suggestions=suggestions,
        out_path=fixed_path,
        segment_ordinal_by_id=result.segment_ordinal_by_id,
    )

    second = parse_docx(fixed_path)
    # Heading text is unchanged.
    original_heading_text = result.text_by_segment_id[seg.id]
    new_heading_text = second.text_by_segment_id[second.document.segments[0].id]
    assert new_heading_text == original_heading_text


def test_writer_handles_missing_segment_id(sample_brief_docx, tmp_path):
    """A suggestion pointing at an unknown segment must not crash."""
    from legal_quality_gate.types import (
        CharRange,
        ObservedStyle,
        Suggestion,
        SuggestionKind,
    )

    result = parse_docx(sample_brief_docx)
    suggestions = [
        Suggestion(
            kind=SuggestionKind.REFORMAT,
            range=CharRange(segment_id="seg-does-not-exist", start=0, end=10),
            new_style=ObservedStyle(font_size_pt=14.0),
            rationale="bogus segment id",
        )
    ]
    out = tmp_path / "noop.docx"
    write_annotated(
        original_path=sample_brief_docx,
        suggestions=suggestions,
        out_path=out,
        segment_ordinal_by_id=result.segment_ordinal_by_id,
    )
    # Document still parses; no exception.
    parse_docx(out)
