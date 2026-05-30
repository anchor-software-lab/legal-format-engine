"""Tests for the FakeAuthorityClient and the Protocol contract."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from legal_authority import AuthorityLookupClient, FakeAuthorityClient
from legal_quality_gate import Authority, GoodLawStatus, Treatment, TreatmentSignal


def test_fake_client_conforms_to_protocol():
    assert isinstance(FakeAuthorityClient(), AuthorityLookupClient)


def test_lookup_returns_canned_authority():
    auth = Authority(
        id="auth-1",
        canonical_cite="Tews v. NHI, LLC, 2010 WI 137",
        name="Tews v. NHI, LLC",
        court="Wisconsin Supreme Court",
        current_status=GoodLawStatus.GOOD_LAW,
        parallel_cites=["330 Wis. 2d 389", "793 N.W.2d 860"],
        last_verified=datetime.now(timezone.utc),
    )
    client = FakeAuthorityClient(by_raw={"2010 WI 137": auth})
    result = asyncio.run(client.lookup(raw_citation="2010 WI 137"))
    assert result is not None
    assert result.canonical_cite == "Tews v. NHI, LLC, 2010 WI 137"
    assert client.calls == ["2010 WI 137"]


def test_lookup_returns_none_for_unknown_citation():
    client = FakeAuthorityClient()
    result = asyncio.run(client.lookup(raw_citation="Made Up v. Nobody, 999 U.S. 999"))
    assert result is None


def test_authority_carries_treatments_and_good_law_status():
    auth = Authority(
        id="auth-1",
        canonical_cite="Bad v. Law, 100 U.S. 1",
        current_status=GoodLawStatus.OVERRULED,
        treatments=[
            Treatment(
                citing_authority_id="auth-overruler",
                signal=TreatmentSignal.NEGATIVE,
                depth=4,
            )
        ],
    )
    assert auth.current_status is GoodLawStatus.OVERRULED
    assert auth.treatments[0].signal is TreatmentSignal.NEGATIVE
