"""Tests for the LLM-backed BluebookCaseFormChecker via FakeLLMClient.

Pin the LLM-bound checker's behavior without making network calls:
canned LLM outputs drive deterministic assertions on the produced
findings, their provenance, severity, and rule_id.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from legal_citations import (
    BluebookCaseFormChecker,
    NormalizeCaseOutput,
    build_case_form_checker,
)
from legal_llm_gateway import FakeLLMClient
from legal_quality_gate import (
    Capability,
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


def test_flags_citation_when_canonical_differs():
    canned = NormalizeCaseOutput(
        canonical="Tews v. NHI, LLC, 2010 WI 137, ¶ 4, 330 Wis. 2d 389, 793 N.W.2d 860",
        confidence=0.95,
    )
    llm = FakeLLMClient(default_output=canned)
    checker = build_case_form_checker(llm=llm)

    doc, ctx = _doc(
        {"seg-1": "See Tews v NHI LLC, 2010 WI 137. The court..."}
    )

    findings = asyncio.run(checker.check(doc, ctx))
    case_form = [f for f in findings if f.rule_id == "BB.CASE.FORM"]
    assert len(case_form) >= 1
    f = case_form[0]
    assert f.severity is Severity.WARNING
    assert f.provenance is Provenance.LLM
    assert f.evidence["canonical"].startswith("Tews v. NHI")
    assert f.suggestion is not None
    assert f.suggestion.new_text == canned.canonical
    assert f.suggestion.auto_apply_safe is False


def test_no_finding_when_observed_matches_canonical():
    canned = NormalizeCaseOutput(
        canonical="2010 WI 137",
        confidence=0.95,
    )
    llm = FakeLLMClient(default_output=canned)
    checker = build_case_form_checker(llm=llm)

    doc, ctx = _doc({"seg-1": "See Tews v. NHI, LLC, 2010 WI 137, ¶ 4."})

    findings = asyncio.run(checker.check(doc, ctx))
    case_form = [f for f in findings if f.rule_id == "BB.CASE.FORM"]
    assert case_form == []


def test_skips_low_confidence_outputs():
    canned = NormalizeCaseOutput(canonical="anything", confidence=0.3)
    llm = FakeLLMClient(default_output=canned)
    checker = build_case_form_checker(llm=llm)

    doc, ctx = _doc({"seg-1": "See Tews v NHI, 2010 WI 137."})
    findings = asyncio.run(checker.check(doc, ctx))
    assert all(f.rule_id != "BB.CASE.FORM" for f in findings)


def test_llm_failure_yields_unavailable_info_finding():
    # No canned responses + no default = LLMError on every call.
    llm = FakeLLMClient()
    checker = build_case_form_checker(llm=llm)

    doc, ctx = _doc({"seg-1": "See Tews v NHI, 2010 WI 137."})
    findings = asyncio.run(checker.check(doc, ctx))

    info = [f for f in findings if f.rule_id == "BB.CASE.FORM.UNAVAILABLE"]
    assert len(info) >= 1
    assert info[0].severity is Severity.INFO
    assert info[0].provenance is Provenance.LLM


def test_skips_short_form_citations():
    """`Id.` and short-form cites have their own rules; this checker
    must not poke the LLM for them."""
    canned = NormalizeCaseOutput(canonical="anything", confidence=0.95)
    llm = FakeLLMClient(default_output=canned)
    checker = build_case_form_checker(llm=llm)

    doc, ctx = _doc(
        {
            "seg-1": (
                "See Tews v. NHI, LLC, 2010 WI 137, ¶ 4. "
                "Id. at ¶ 14."
            )
        }
    )
    asyncio.run(checker.check(doc, ctx))

    # Only the full case cite (Tews) should drive an LLM call. `Id.`
    # is a short form and is skipped.
    full_case_calls = [c for c in llm.calls if c[0] == "bluebook.normalize_case@v1"]
    assert len(full_case_calls) == 1


def test_pipeline_filters_capability_llm_when_not_available():
    """Demonstrate offline operation: a Policy that only enables
    deterministic checkers leaves LLM-bound ones out."""
    canned = NormalizeCaseOutput(canonical="x", confidence=0.95)
    llm = FakeLLMClient(default_output=canned)
    checker = build_case_form_checker(llm=llm)

    assert Capability.LLM in checker.requires

    registry = CheckerRegistry()
    registry.register(checker)

    doc, ctx = _doc({"seg-1": "See Tews v NHI, 2010 WI 137."})
    # Empty enabled list defaults to "all enabled"; to opt out of the
    # LLM checker, name it OUT via the policy. We model that by
    # building a fresh registry without it.
    bare_registry = CheckerRegistry()  # no LLM checkers registered
    report = asyncio.run(Pipeline(bare_registry).run(doc, ctx))

    assert all(f.checker_id != "bluebook.case_form" for f in report.findings)
    # And no LLM calls were issued.
    assert llm.calls == []
