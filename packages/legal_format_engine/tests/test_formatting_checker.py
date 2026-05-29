"""Tests for the formatting.spec_diff checker that wraps merge_with_rules."""

from __future__ import annotations

import asyncio

from legal_format_engine import build_formatting_checker
from legal_format_engine.ml_integration.format_consumer import (
    FormatSpec,
    LearnedTypography,
)
from legal_quality_gate import (
    CheckContext,
    CheckerRegistry,
    Document,
    ObservedStyle,
    Pipeline,
    Provenance,
    Segment,
    SegmentKind,
    Severity,
)


def _doc(observed: ObservedStyle) -> Document:
    return Document(
        id="doc-1",
        sha256="0" * 64,
        segments=[
            Segment(
                id="seg-1",
                kind=SegmentKind.PARAGRAPH,
                ordinal=0,
                text_hash="abc",
                char_length=100,
                style_observed=observed,
            )
        ],
    )


def _ctx() -> CheckContext:
    return CheckContext(text_loader=lambda seg: "x" * seg.char_length)


def test_no_findings_when_observed_matches_defaults():
    checker = build_formatting_checker(rules={})
    document = _doc(
        ObservedStyle(
            font_name="Times New Roman",
            font_size_pt=13.0,
            line_spacing=2.0,
            margin_top_inches=1.0,
        )
    )

    findings = checker.check(document, _ctx())

    assert findings == []


def test_finding_when_observed_violates_rule():
    rules = {"page_format": {"font_size_pt": 13.0}}
    checker = build_formatting_checker(rules=rules)
    document = _doc(ObservedStyle(font_size_pt=12.0))

    findings = checker.check(document, _ctx())

    assert len(findings) == 1
    f = findings[0]
    assert f.rule_id == "FORMAT.FONT.SIZE"
    assert f.severity is Severity.ERROR  # rule-sourced violations are errors
    assert f.evidence["observed"] == 12.0
    assert f.evidence["expected"] == 13.0
    assert f.evidence["source"] == "rule"
    assert f.suggestion is not None
    assert f.suggestion.auto_apply_safe is True
    assert f.suggestion.new_style.font_size_pt == 13.0
    assert f.provenance is Provenance.RULE


def test_finding_when_observed_violates_ml_learned_value():
    ml_spec = FormatSpec(
        document_count=10,
        overall_confidence=0.9,
        typography=LearnedTypography(
            font_family="Garamond",
            font_family_confidence=0.95,
        ),
    )
    checker = build_formatting_checker(rules={}, ml_spec=ml_spec)
    document = _doc(ObservedStyle(font_name="Arial"))

    findings = checker.check(document, _ctx())

    assert len(findings) == 1
    f = findings[0]
    assert f.rule_id == "FORMAT.FONT.NAME"
    assert f.severity is Severity.WARNING  # ML-sourced are not errors
    assert f.evidence["source"] == "ml_learned"
    assert f.suggestion is not None
    assert f.suggestion.auto_apply_safe is False  # ML values are not auto-applied
    assert f.provenance is Provenance.ML


def test_rule_overrides_ml_when_both_present():
    ml_spec = FormatSpec(
        document_count=10,
        overall_confidence=0.9,
        typography=LearnedTypography(
            font_size_pt=11.0,
            font_size_confidence=0.95,
        ),
    )
    rules = {"page_format": {"font_size_pt": 13.0}}
    checker = build_formatting_checker(rules=rules, ml_spec=ml_spec)
    document = _doc(ObservedStyle(font_size_pt=12.0))

    findings = checker.check(document, _ctx())

    assert len(findings) == 1
    assert findings[0].evidence["expected"] == 13.0
    assert findings[0].evidence["source"] == "rule"


def test_pipeline_integration():
    registry = CheckerRegistry()
    rules = {"page_format": {"font_size_pt": 13.0}}
    registry.register(build_formatting_checker(rules=rules))

    document = _doc(ObservedStyle(font_size_pt=12.0))
    report = asyncio.run(Pipeline(registry).run(document, _ctx()))

    assert len(report.findings) == 1
    assert report.score < 100  # an error subtracted from base
