"""CourtListener-backed `AuthorityLookupClient`.

Uses CourtListener's REST v4 API (https://www.courtlistener.com/help/api/rest/).

- Lookups go to `POST /api/rest/v4/citation-lookup/` which accepts a
  raw citation string and returns the matching opinion cluster
  (including parallel cites, court, year, and any negative subsequent
  history).
- Authentication: `Authorization: Token <CL_API_TOKEN>` header.
  Token-based, free tier available.
- Network is gated by an injected `httpx.AsyncClient` so tests can
  swap an `httpx.MockTransport` for offline determinism.

Good-law derivation: CourtListener provides a `citing_cases_negative`
treatment indicator and the OAA (Opinions Affected by Authorities)
mapping. v1 surfaces `GoodLawStatus.GOOD_LAW` vs `QUESTIONED` based on
treatment counts; the full citator graph + materialized view lands
when `legal_authority_scraper` ships in v2 — until then the OAA
hints are conservative but useful.

Live smoke tests against the real API are kept in a separate file
gated on `ANCHOR_CL_LIVE=1`; PR CI uses only the MockTransport-driven
tests below.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from legal_quality_gate.types import (
    Authority,
    GoodLawStatus,
    Treatment,
    TreatmentSignal,
)


DEFAULT_BASE_URL = "https://www.courtlistener.com/api/rest/v4"
DEFAULT_TIMEOUT_SECONDS = 15.0


class CourtListenerClient:
    """Implements `AuthorityLookupClient` against CourtListener REST v4."""

    def __init__(
        self,
        *,
        api_token: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_token = api_token or os.environ.get("CL_API_TOKEN", "")
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._timeout = timeout
        self._cache: dict[str, Authority | None] = {}

    async def lookup(
        self,
        *,
        raw_citation: str,
        jurisdiction_hint: str | None = None,
    ) -> Authority | None:
        """Resolve a raw citation string to a `Authority`, or `None` if
        CourtListener has no matching opinion."""
        cache_key = f"{raw_citation}|{jurisdiction_hint or ''}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = await self._call_citation_lookup(raw_citation)
        authority = self._authority_from_response(result, raw_citation)
        self._cache[cache_key] = authority
        return authority

    async def _call_citation_lookup(self, raw_citation: str) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        if self._api_token:
            headers["Authorization"] = f"Token {self._api_token}"

        url = f"{self._base_url}/citation-lookup/"
        async with httpx.AsyncClient(
            timeout=self._timeout, transport=self._transport
        ) as client:
            response = await client.post(
                url,
                data={"text": raw_citation},
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    def _authority_from_response(
        self, payload: dict[str, Any], raw_citation: str
    ) -> Authority | None:
        """Map a CourtListener citation-lookup payload to an Authority.

        The endpoint returns one entry per citation token recognized in
        the input; for our single-citation lookups we read the first
        successful match.
        """
        # Both v3 and v4 wrap matches under a `citations` array; v4 uses
        # `clusters` as the resolved opinion list.
        entries = payload.get("citations") or [payload]
        for entry in entries:
            clusters = entry.get("clusters") or []
            if not clusters and entry.get("status") not in (None, 200):
                continue
            cluster = clusters[0] if clusters else entry
            if not cluster:
                continue

            decided = _parse_date(cluster.get("date_filed"))
            parallel = [
                c.get("cite") for c in cluster.get("citations", []) if c.get("cite")
            ]
            current_status = _status_from_cluster(cluster)
            treatments = _treatments_from_cluster(cluster)

            return Authority(
                id=str(cluster.get("id") or cluster.get("absolute_url") or raw_citation),
                canonical_cite=_canonical_cite(cluster, raw_citation),
                name=cluster.get("case_name") or cluster.get("caseName"),
                court=cluster.get("court") or cluster.get("court_id"),
                decided=decided,
                parallel_cites=parallel,
                treatments=treatments,
                current_status=current_status,
                last_verified=datetime.now(timezone.utc),
            )
        return None


def _canonical_cite(cluster: dict[str, Any], fallback: str) -> str:
    cites = cluster.get("citations") or []
    for c in cites:
        if c.get("type") == "official" and c.get("cite"):
            return c["cite"]
    if cites and cites[0].get("cite"):
        return cites[0]["cite"]
    return fallback


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _status_from_cluster(cluster: dict[str, Any]) -> GoodLawStatus:
    """Map the OAA / treatment hints we get from CL into our enum.

    Conservative: anything explicitly flagged as overruled/reversed is
    surfaced; "questioned by" / "limited by" treatments downgrade to
    QUESTIONED; otherwise the opinion is presumed good law. Full
    citator graph computation moves into the scraper in v2.
    """
    negative = cluster.get("negative_treatments") or []
    overruled_kinds = {"overruled", "reversed", "vacated", "abrogated"}
    questioned_kinds = {"questioned", "limited", "distinguished", "criticized"}

    for treatment in negative:
        kind = (treatment.get("kind") or "").lower()
        if any(o in kind for o in overruled_kinds):
            if "vacated" in kind:
                return GoodLawStatus.VACATED
            if "reversed" in kind:
                return GoodLawStatus.REVERSED
            if "abrogated" in kind:
                return GoodLawStatus.SUPERSEDED
            return GoodLawStatus.OVERRULED

    if any(
        any(q in (t.get("kind") or "").lower() for q in questioned_kinds)
        for t in negative
    ):
        return GoodLawStatus.QUESTIONED

    return GoodLawStatus.GOOD_LAW


def _treatments_from_cluster(cluster: dict[str, Any]) -> list[Treatment]:
    out: list[Treatment] = []
    for t in cluster.get("negative_treatments") or []:
        signal = _treatment_signal(t.get("kind"))
        out.append(
            Treatment(
                citing_authority_id=str(t.get("citing_opinion_id") or ""),
                signal=signal,
                depth=int(t.get("depth") or 1),
                source="courtlistener",
            )
        )
    return out


def _treatment_signal(kind: str | None) -> TreatmentSignal:
    if not kind:
        return TreatmentSignal.NEUTRAL
    k = kind.lower()
    if any(neg in k for neg in ("overrul", "revers", "vacated", "abrogat")):
        return TreatmentSignal.NEGATIVE
    if any(soft in k for soft in ("question", "limited", "criticized")):
        return TreatmentSignal.NEGATIVE
    if "distinguish" in k:
        return TreatmentSignal.DISTINGUISHING
    if any(pos in k for pos in ("affirm", "follow", "approv")):
        return TreatmentSignal.POSITIVE
    return TreatmentSignal.NEUTRAL


# Convenience for the rare URL-encoded path we'd want to build by hand.
def _encode(value: str) -> str:
    return quote(value, safe="")
