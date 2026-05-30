"""Tests for the Bluebook signal + pinpoint checkers via the pipeline."""

from __future__ import annotations

import asyncio
import uuid

from legal_citations import (
    BluebookSignalChecker,
    PinpointMissingChecker,
    build_pinpoint_checker,
    build_signal_checker,
    get_or_extract_citations,
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


def _doc(text_by_segment: dict[str, str]) -> tuple[Document, CheckContext]:
    segments = []
    for i, (sid, text) in enumerate(text_by_segment.items()):
        segments.append(
            Segment(
                id=sid,
                kind=SegmentKind.PARAGRAPH,
                ordinal=i,
                text_hash=str(uuid.uuid4()),
                char_length=len(text),
                style_observed=ObservedStyle(),
            )
        )
    doc = Document(id="doc-1", sha256="0" * 64, segments=segments)
    ctx = CheckContext(text_loader=lambda seg: text_by_segment[seg.id])
    return doc, ctx


def test_signal_checker_flags_unknown_signal():
    doc, ctx = _doc(
        {
            "seg-1": "Foo. See, also, Tews v. NHI, LLC, 2010 WI 137, ¶ 4.",
        }
    )
    findings = BluebookSignalChecker().check(doc, ctx)
    assert any(f.rule_id == "BB.SIGNAL.UNKNOWN" for f in findings)


def test_signal_checker_accepts_canonical_signals():
    doc, ctx = _doc(
        {
            "seg-1": (
                "Foo. See Tews v. NHI, LLC, 2010 WI 137, ¶ 4. "
                "See also Brown v. Holiday, 2008 WI 49, ¶ 12. "
                "But see Smith v. Jones, 100 U.S. 1, 5 (1990)."
            ),
        }
    )
    findings = BluebookSignalChecker().check(doc, ctx)
    assert not any(f.rule_id == "BB.SIGNAL.UNKNOWN" for f in findings)


def test_signal_checker_emits_no_finding_when_no_signal():
    doc, ctx = _doc(
        {"seg-1": "Tews v. NHI, LLC, 2010 WI 137, ¶ 4, governs."},
    )
    assert BluebookSignalChecker().check(doc, ctx) == []


def test_pinpoint_checker_flags_missing_pinpoint():
    doc, ctx = _doc(
        {"seg-1": "See Brown v. Holiday, 2008 WI 49. The court held otherwise."}
    )
    findings = PinpointMissingChecker().check(doc, ctx)
    assert len(findings) == 1
    f = findings[0]
    assert f.rule_id == "BB.PINPOINT.MISSING"
    assert f.severity is Severity.WARNING
    assert f.provenance is Provenance.RULE


def test_pinpoint_checker_accepts_cite_with_pinpoint():
    doc, ctx = _doc(
        {"seg-1": "See Tews v. NHI, LLC, 2010 WI 137, ¶ 4, 330 Wis. 2d 389."}
    )
    findings = PinpointMissingChecker().check(doc, ctx)
    assert findings == []


def test_extraction_is_cached_across_checkers():
    doc, ctx = _doc(
        {"seg-1": "See Brown v. Holiday, 2008 WI 49."}
    )
    first = get_or_extract_citations(doc, ctx)
    second = get_or_extract_citations(doc, ctx)
    # Same object — proves the cache hit.
    assert first is second


def test_pipeline_runs_both_citation_checkers():
    doc, ctx = _doc(
        {
            "seg-1": (
                "Foo. See, also, Tews v. NHI, LLC, 2010 WI 137. "
                "See Brown v. Holiday, 2008 WI 49."
            ),
        }
    )
    registry = CheckerRegistry()
    registry.register(build_signal_checker())
    registry.register(build_pinpoint_checker())

    report = asyncio.run(Pipeline(registry).run(doc, ctx))

    rule_ids = {f.rule_id for f in report.findings}
    assert "BB.SIGNAL.UNKNOWN" in rule_ids
    assert "BB.PINPOINT.MISSING" in rule_ids
