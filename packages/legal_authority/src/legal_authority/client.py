"""The AuthorityLookupClient Protocol — what citation checkers depend on.

v0 ships the contract types and a `FakeAuthorityClient` for offline
tests. The real CourtListener-backed client lands in v1.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from legal_quality_gate.types import Authority


@runtime_checkable
class AuthorityLookupClient(Protocol):
    """Single-citation lookup. The pipeline batches calls when possible."""

    async def lookup(
        self,
        *,
        raw_citation: str,
        jurisdiction_hint: str | None = None,
    ) -> Authority | None: ...


class FakeAuthorityClient:
    """Returns canned Authority records keyed by raw citation string.

    Used by tests for citation-existence and good-law checkers that
    need to verify behavior without hitting CourtListener.
    """

    def __init__(self, by_raw: dict[str, Authority] | None = None) -> None:
        self._by_raw = by_raw or {}
        self.calls: list[str] = []

    async def lookup(
        self,
        *,
        raw_citation: str,
        jurisdiction_hint: str | None = None,
    ) -> Authority | None:
        self.calls.append(raw_citation)
        return self._by_raw.get(raw_citation)
