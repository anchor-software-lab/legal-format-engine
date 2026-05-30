"""Tests for the CitationExistsChecker via FakeAuthorityClient."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from legal_authority import FakeAuthorityClient
from legal_citations import build_citations_exists_checker
from legal_quality_gate import (
    Authority,
    Capability,
    CheckContext,
    Document,
    GoodLawStatus,
    ObservedStyle,
    Provenance,
    Segment,
    SegmentKind,
    Severity,
    Treatment,
    TreatmentSignal,
)


def _doc(text_by_segment: dict[str, str], jurisdiction: str | None = None) -> tuple[Document, CheckContext]:
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
    doc = Document(
        id="doc-1",
        sha256="0" * 64,
        segments=segments,
        jurisdiction_hints=[jurisdiction] if jurisdiction else [],
    )
    ctx = CheckContext(text_loader=lambda seg: text_by_segment[seg.id])
    return doc, ctx


def _good_law_authority() -> Authority:
    return Authority(
        id="auth-1",
        canonical_cite="Tews v. NHI, LLC, 2010 WI 137",
        name="Tews v. NHI, LLC",
        court="wis",
        current_status=GoodLawStatus.GOOD_LAW,
        last_verified=datetime.now(timezone.utc),
    )


def _overruled_authority() -> Authority:
    return Authority(
        id="auth-2",
        canonical_cite="410 U.S. 113",
        name="Roe v. Wade",
        court="scotus",
        current_status=GoodLawStatus.OVERRULED,
        treatments=[
            Treatment(
                citing_authority_id="dobbs",
                signal=TreatmentSignal.NEGATIVE,
                depth=4,
            )
        ],
    )


def test_checker_requires_network_and_authority_db():
    checker = build_citations_exists_checker(authority=FakeAuthorityClient())
    assert Capability.NETWORK in checker.requires
    assert Capability.AUTHORITY_DB in checker.requires


def test_flags_ghost_citation_when_no_match():
    authority = FakeAuthorityClient(by_raw={})  # nothing matches
    checker = build_citations_exists_checker(authority=authority)

    doc, ctx = _doc({"seg-1": "See Tews v. NHI, LLC, 2010 WI 137, ¶ 4."})
    findings = asyncio.run(checker.check(doc, ctx))

    ghost = [f for f in findings if f.rule_id == "CITE.GHOST"]
    assert len(ghost) == 1
    f = ghost[0]
    assert f.severity is Severity.ERROR
    assert f.provenance is Provenance.RULE
    assert "Tews" in str(f.evidence)


def test_no_ghost_finding_when_authority_resolves():
    auth_record = _good_law_authority()
    # The fake matches against the citation's raw_text (the
    # reporter token from eyecite, e.g. "2010 WI 137").
    authority = FakeAuthorityClient(by_raw={"2010 WI 137": auth_record})
    checker = build_citations_exists_checker(authority=authority)

    doc, ctx = _doc({"seg-1": "See Tews v. NHI, LLC, 2010 WI 137, ¶ 4."})
    findings = asyncio.run(checker.check(doc, ctx))

    assert not any(f.rule_id == "CITE.GHOST" for f in findings)


def test_flags_overruled_citation():
    auth_record = _overruled_authority()
    authority = FakeAuthorityClient(by_raw={"410 U.S. 113": auth_record})
    checker = build_citations_exists_checker(authority=authority)

    doc, ctx = _doc({"seg-1": "See Roe v. Wade, 410 U.S. 113, 118 (1973)."})
    findings = asyncio.run(checker.check(doc, ctx))

    overruled = [f for f in findings if f.rule_id == "CITE.GOOD_LAW.OVERRULED"]
    assert len(overruled) == 1
    assert overruled[0].severity is Severity.ERROR


def test_skips_short_form_citations():
    """Id./supra/short forms don't get authority lookups."""
    authority = FakeAuthorityClient()
    checker = build_citations_exists_checker(authority=authority)

    doc, ctx = _doc(
        {
            "seg-1": (
                "See Tews v. NHI, LLC, 2010 WI 137, ¶ 4. "
                "Id. at ¶ 14."
            )
        }
    )
    asyncio.run(checker.check(doc, ctx))

    # The Id. cite must not have triggered a lookup.
    assert all("Id." not in raw for raw in authority.calls)


def test_caches_authority_lookups_across_citations():
    """The same raw citation appearing twice yields one lookup."""
    authority = FakeAuthorityClient(
        by_raw={"2010 WI 137": _good_law_authority()}
    )
    checker = build_citations_exists_checker(authority=authority)

    doc, ctx = _doc(
        {
            "seg-1": "See Tews v. NHI, LLC, 2010 WI 137, ¶ 4.",
            "seg-2": "Tews v. NHI, LLC, 2010 WI 137, ¶ 5, again.",
        }
    )
    asyncio.run(checker.check(doc, ctx))

    lookup_count = sum(1 for raw in authority.calls if raw == "2010 WI 137")
    assert lookup_count == 1


def test_lookup_failure_yields_info_finding_not_crash():
    class Boom:
        async def lookup(self, **kwargs):
            raise RuntimeError("upstream timeout")

    checker = build_citations_exists_checker(authority=Boom())
    doc, ctx = _doc({"seg-1": "See Tews v. NHI, LLC, 2010 WI 137, ¶ 4."})
    findings = asyncio.run(checker.check(doc, ctx))

    unavailable = [f for f in findings if f.rule_id == "CITE.LOOKUP.UNAVAILABLE"]
    assert len(unavailable) == 1
    assert unavailable[0].severity is Severity.INFO


def test_jurisdiction_hint_propagated_to_authority_client():
    captured: list[str | None] = []

    class Capturing:
        async def lookup(self, *, raw_citation, jurisdiction_hint=None):
            captured.append(jurisdiction_hint)
            return None

    checker = build_citations_exists_checker(authority=Capturing())
    doc, ctx = _doc(
        {"seg-1": "See Tews v. NHI, LLC, 2010 WI 137, ¶ 4."},
        jurisdiction="WI",
    )
    asyncio.run(checker.check(doc, ctx))

    assert "WI" in captured
