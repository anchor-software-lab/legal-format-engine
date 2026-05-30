"""Legal authority lookup + good-law tracking.

v1 ships:
- `AuthorityLookupClient` Protocol: async `lookup(raw_citation,
  jurisdiction_hint)` returning `Authority | None`.
- `FakeAuthorityClient`: deterministic stub for tests.
- `CourtListenerClient`: real implementation against the CL REST v4
  citation-lookup endpoint, with token-based auth and a configurable
  `httpx.AsyncBaseTransport` for testing.

The `Authority`, `Treatment`, `GoodLawStatus`, `TreatmentSignal`
models live in `legal_quality_gate.types` because they're part of the
cross-package domain model that checkers, the API, and the JSON
schemas all consume.

v2 adds the WI courts scraper, the citator graph, and a
materialized good-law view alongside (not replacing) CourtListener.
"""

from legal_authority.client import AuthorityLookupClient, FakeAuthorityClient
from legal_authority.courtlistener import CourtListenerClient

__all__ = [
    "AuthorityLookupClient",
    "CourtListenerClient",
    "FakeAuthorityClient",
]
