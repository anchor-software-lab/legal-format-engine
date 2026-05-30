"""FastAPI SaaS surface.

v1 alpha public surface:
- `create_app(deps)` — FastAPI app factory. Tests build one per case;
  `uvicorn legal_api.main:app` boots a single default instance.
- `AppDeps` — wiring bundle: store, blobs, api_key_resolver,
  llm_client, authority_client, policy_loader, registry_builder.
- `InMemoryStore`, `FilesystemBlobStore`, `InMemoryApiKeyResolver` —
  defaults useful for v1 alpha and tests. Swap Postgres / S3 / Auth0
  behind the same Protocols.

Routes implement the OpenAPI skeleton in `schemas/openapi.yaml`:
`POST /v1/documents`, `POST /v1/runs`, `GET /v1/runs/{id}`,
`GET /v1/runs/{id}/annotated.docx`, `GET /v1/health`.

Phase D adds the envelope-encryption upload flow and suggestion
:apply / :reject endpoints; for v1 alpha the API accepts plaintext
docx uploads with operator-managed at-rest encryption.
"""

from legal_api.blobs import BlobStore, FilesystemBlobStore
from legal_api.envelope import (
    EncryptedPayload,
    decrypt_document,
    encrypt_document,
    encrypt_for_upload,
    generate_dek,
    generate_keypair_pem,
    unwrap_dek,
    wrap_dek,
)
from legal_api.keyring import EnvelopeKeyring, InMemoryKeyring, KeyringError
from legal_api.main import AppDeps, create_app
from legal_api.security import (
    ApiKeyResolver,
    InMemoryApiKeyResolver,
    RequestPrincipal,
    require_principal,
    require_scope,
)
from legal_api.store import (
    DocumentRecord,
    InMemoryStore,
    RunRecord,
    Store,
    new_id,
)

__all__ = [
    "ApiKeyResolver",
    "AppDeps",
    "BlobStore",
    "DocumentRecord",
    "EncryptedPayload",
    "EnvelopeKeyring",
    "FilesystemBlobStore",
    "InMemoryApiKeyResolver",
    "InMemoryKeyring",
    "InMemoryStore",
    "KeyringError",
    "RequestPrincipal",
    "RunRecord",
    "Store",
    "create_app",
    "decrypt_document",
    "encrypt_document",
    "encrypt_for_upload",
    "generate_dek",
    "generate_keypair_pem",
    "new_id",
    "require_principal",
    "require_scope",
    "unwrap_dek",
    "wrap_dek",
]
