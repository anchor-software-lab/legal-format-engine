"""Server-side key management for the envelope-encryption flow.

The `EnvelopeKeyring` Protocol abstracts where org private keys live.
Two implementations ship:

- `InMemoryKeyring`: holds private keys keyed by org_id. Useful for
  tests and v1 alpha self-hosted deployments where the operator
  bootstraps keys directly.
- `SessionUnwrapKeyring` (planned, v1.5): production pattern where the
  server doesn't hold the private key at all — it calls back to the
  customer's plugin (Office Add-in or a CLI sidecar) which decrypts
  the DEK and returns it over a short-lived authenticated session.

The Protocol lets us swap implementations without touching the run
pipeline. Tests use `InMemoryKeyring`; production wiring picks
whichever matches the deployment's trust model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from legal_api.envelope import unwrap_dek


class EnvelopeKeyring(Protocol):
    """Resolve an org's private key well enough to unwrap a DEK."""

    def unwrap(self, *, org_id: str, wrapped_dek: bytes) -> bytes: ...

    def public_key_pem(self, org_id: str) -> bytes | None:
        """Return the org's registered public key, or None if unknown.

        Used by the upload endpoint to verify that the org has a key
        registered before accepting an encrypted upload.
        """
        ...


@dataclass
class InMemoryKeyring:
    """Holds private keys directly. v1 alpha and tests."""

    private_keys_by_org: dict[str, bytes] = field(default_factory=dict)
    public_keys_by_org: dict[str, bytes] = field(default_factory=dict)

    def register(self, *, org_id: str, private_pem: bytes, public_pem: bytes) -> None:
        self.private_keys_by_org[org_id] = private_pem
        self.public_keys_by_org[org_id] = public_pem

    def unwrap(self, *, org_id: str, wrapped_dek: bytes) -> bytes:
        private_pem = self.private_keys_by_org.get(org_id)
        if private_pem is None:
            raise KeyError(f"no private key registered for org {org_id!r}")
        return unwrap_dek(wrapped_dek, private_pem)

    def public_key_pem(self, org_id: str) -> bytes | None:
        return self.public_keys_by_org.get(org_id)


class KeyringError(Exception):
    """Raised when the keyring cannot unwrap a DEK."""
