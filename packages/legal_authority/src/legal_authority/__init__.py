"""Legal authority lookup + good-law tracking.

v0 ships the contract: `AuthorityLookupClient` Protocol plus a
`FakeAuthorityClient` for tests. The CourtListener-backed client and
good-law citator graph land in v1.

The `Authority`, `Treatment`, `GoodLawStatus`, `TreatmentSignal`
models live in `legal_quality_gate.types` because they're part of the
cross-package domain model that checkers, the API, and the JSON
schemas all consume.
"""

from legal_authority.client import AuthorityLookupClient, FakeAuthorityClient

__all__ = [
    "AuthorityLookupClient",
    "FakeAuthorityClient",
]
