"""End-to-end: parse a real docx → run the formatting checker → assert findings.

This is the first real proof that the foundation works on a docx
instead of a synthetic in-memory `Document`.
"""

from __future__ import annotations

import asyncio

from legal_docx import parse_docx
from legal_format_engine import build_formatting_checker
from legal_quality_gate import (
    CheckContext,
    CheckerRegistry,
    Pipeline,
    Provenance,
    Severity,
)


def test_formatting_checker_flags_undersized_body_font(sample_brief_docx):
    """The fixture's body paragraph is 12pt; the rule expects 13pt.

    The formatting checker should raise a rule-sourced error finding
    against the body paragraph and a matching error against the block
    quote (which it also flags, since the rule is document-wide). The
    conclusion paragraph is 13pt so it should not be flagged.
    """
    result = parse_docx(sample_brief_docx)
    rules = {"page_format": {"font_size_pt": 13.0}}
    registry = CheckerRegistry()
    registry.register(build_formatting_checker(rules=rules))

    ctx = CheckContext(text_loader=result.text_loader)
    report = asyncio.run(Pipeline(registry).run(result.document, ctx))

    font_size_findings = [
        f for f in report.findings if f.rule_id == "FORMAT.FONT.SIZE"
    ]
    # Body paragraph (12pt) flagged; conclusion (13pt) not flagged.
    # Heading and block quote sizes may or may not be flagged depending
    # on how python-docx's heading style resolves font size, so we
    # assert on the body paragraph specifically.
    body_segment_id = result.document.segments[1].id
    assert any(f.segment_id == body_segment_id for f in font_size_findings)

    body_finding = next(
        f for f in font_size_findings if f.segment_id == body_segment_id
    )
    assert body_finding.severity is Severity.ERROR
    assert body_finding.provenance is Provenance.RULE
    assert body_finding.evidence["observed"] == 12.0
    assert body_finding.evidence["expected"] == 13.0
    assert body_finding.suggestion is not None
    assert body_finding.suggestion.auto_apply_safe is True
    assert body_finding.suggestion.new_style.font_size_pt == 13.0

    # Score should have dropped from 100 by at least the body finding's
    # cost (10 for error).
    assert report.score <= 90.0
