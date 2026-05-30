"""Tests for CourtListenerClient using httpx.MockTransport.

httpx ships a built-in MockTransport so we don't need vcrpy/respx for
the v1 test surface. A future live-smoke test file
(test_courtlistener_live.py, gated on ANCHOR_CL_LIVE=1) will hit the
real API to catch schema drift; that's deliberately not run in PR CI.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from legal_authority import AuthorityLookupClient, CourtListenerClient
from legal_quality_gate import GoodLawStatus


def _good_law_payload() -> dict:
    return {
        "citations": [
            {
                "clusters": [
                    {
                        "id": 12345,
                        "case_name": "Tews v. NHI, LLC",
                        "court": "wis",
                        "date_filed": "2010-12-23",
                        "citations": [
                            {"cite": "2010 WI 137", "type": "neutral"},
                            {"cite": "330 Wis. 2d 389", "type": "official"},
                            {"cite": "793 N.W.2d 860", "type": "parallel"},
                        ],
                        "negative_treatments": [],
                    }
                ]
            }
        ]
    }


def _overruled_payload() -> dict:
    return {
        "citations": [
            {
                "clusters": [
                    {
                        "id": 99,
                        "case_name": "Roe v. Wade",
                        "court": "scotus",
                        "date_filed": "1973-01-22",
                        "citations": [{"cite": "410 U.S. 113", "type": "official"}],
                        "negative_treatments": [
                            {
                                "kind": "overruled by",
                                "citing_opinion_id": 22,
                                "depth": 4,
                            }
                        ],
                    }
                ]
            }
        ]
    }


def _empty_payload() -> dict:
    return {"citations": [{"clusters": [], "status": 404}]}


def _build_client(handler) -> CourtListenerClient:
    transport = httpx.MockTransport(handler)
    return CourtListenerClient(api_token="test-token", transport=transport)


def test_courtlistener_client_conforms_to_protocol():
    client = _build_client(lambda req: httpx.Response(200, json=_good_law_payload()))
    assert isinstance(client, AuthorityLookupClient)


def test_lookup_returns_authority_for_good_law_citation():
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(200, json=_good_law_payload())

    client = _build_client(handler)
    result = asyncio.run(client.lookup(raw_citation="2010 WI 137"))

    assert result is not None
    assert result.name == "Tews v. NHI, LLC"
    assert result.court == "wis"
    assert result.current_status is GoodLawStatus.GOOD_LAW
    assert "330 Wis. 2d 389" in result.parallel_cites
    assert "793 N.W.2d 860" in result.parallel_cites
    # Token sent in header.
    assert seen_requests[0].headers["authorization"] == "Token test-token"
    # POST body carries the citation as form-encoded `text`.
    assert b"text=2010" in seen_requests[0].content


def test_lookup_marks_overruled_status():
    client = _build_client(
        lambda req: httpx.Response(200, json=_overruled_payload())
    )
    result = asyncio.run(client.lookup(raw_citation="410 U.S. 113"))
    assert result is not None
    assert result.current_status is GoodLawStatus.OVERRULED
    assert len(result.treatments) == 1
    assert result.treatments[0].depth == 4


def test_lookup_returns_none_when_no_match():
    client = _build_client(
        lambda req: httpx.Response(200, json=_empty_payload())
    )
    result = asyncio.run(client.lookup(raw_citation="999 Fake 999"))
    assert result is None


def test_lookup_caches_repeated_calls():
    calls: list[int] = []

    def handler(req):
        calls.append(1)
        return httpx.Response(200, json=_good_law_payload())

    client = _build_client(handler)
    asyncio.run(client.lookup(raw_citation="2010 WI 137"))
    asyncio.run(client.lookup(raw_citation="2010 WI 137"))
    assert len(calls) == 1  # second hit served from cache


def test_lookup_raises_on_5xx():
    client = _build_client(lambda req: httpx.Response(503, text="upstream down"))
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(client.lookup(raw_citation="anything"))
