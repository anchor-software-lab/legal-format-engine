"""FastAPI application for the Anchor Quality Gate SaaS surface.

v1 alpha:
- API-key auth (X-Anchor-API-Key header).
- Synchronous pipeline runs (no Redis/RQ yet; runs complete
  in-request, which is fine for documents under a few hundred KB).
- In-memory store + filesystem blob store. Production wiring swaps
  Postgres + S3/R2 behind the same Protocols (see store.py / blobs.py).
- Envelope encryption is a Phase D follow-up; for v1 alpha the API
  accepts plaintext docx uploads and the operator is responsible for
  at-rest disk encryption.

Routes wired up here mirror the OpenAPI skeleton in
schemas/openapi.yaml. The OpenAPI is the source of truth for clients
(TS, C#); FastAPI auto-publishes its own openapi.json at /openapi.json
which we'll diff-test against schemas/openapi.yaml in v1.5.
"""

from __future__ import annotations

import asyncio
import io
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from legal_citations import (
    build_case_form_checker,
    build_citations_exists_checker,
    build_pinpoint_checker,
    build_short_form_checker,
    build_signal_checker,
)
from legal_docx import parse_docx, write_annotated
from legal_format_engine import build_formatting_checker
from legal_quality_gate import (
    CheckContext,
    CheckerRegistry,
    Pipeline,
    Policy,
    QualityReport,
)

from legal_api.blobs import BlobStore, FilesystemBlobStore
from legal_api.envelope import decrypt_document
from legal_api.keyring import EnvelopeKeyring, InMemoryKeyring
from legal_api.security import (
    ApiKeyResolver,
    InMemoryApiKeyResolver,
    RequestPrincipal,
    require_principal,
)
from legal_api.store import (
    DocumentRecord,
    InMemoryStore,
    RunRecord,
    Store,
    new_id,
)

if TYPE_CHECKING:
    from legal_authority import AuthorityLookupClient
    from legal_llm_gateway import LLMClient


# -------- Request / response models --------


class DocumentRef(BaseModel):
    document_id: str


class CreateRunRequest(BaseModel):
    document_id: str
    policy_id: str | None = None
    mode: str = Field(default="report", pattern="^(report|autofix)$")


class RunRef(BaseModel):
    run_id: str
    status_url: str
    status: str


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0-draft"


class EncryptedUploadRequest(BaseModel):
    """Envelope-encrypted document upload payload.

    Fields are base64-encoded so the JSON wire shape works for any
    transport that doesn't speak binary. Server decodes once and stores
    raw bytes — no base64 lives in the blob store.
    """

    ciphertext_b64: str
    nonce_b64: str
    wrapped_dek_b64: str
    sha256: str = Field(
        ...,
        pattern="^[a-f0-9]{64}$",
        description="SHA-256 of the original plaintext, for integrity check after decrypt.",
    )
    original_filename: str | None = None


class PublicKeyResponse(BaseModel):
    org_id: str
    public_key_pem: str


# -------- App factory --------


@dataclass
class AppDeps:
    """Wiring bundle. Swap implementations to wire Postgres / S3 / OIDC."""

    store: Store = field(default_factory=InMemoryStore)
    blobs: BlobStore | None = None
    api_key_resolver: ApiKeyResolver = field(default_factory=InMemoryApiKeyResolver)
    keyring: EnvelopeKeyring | None = None
    llm_client: "LLMClient | None" = None
    authority_client: "AuthorityLookupClient | None" = None
    policy_loader: Any = None  # callable(policy_id) -> Policy
    registry_builder: Any = None  # callable(rules, llm_client, authority_client) -> CheckerRegistry


def create_app(deps: AppDeps | None = None) -> FastAPI:
    deps = deps or AppDeps()
    if deps.blobs is None:
        deps.blobs = FilesystemBlobStore(root=Path(tempfile.mkdtemp(prefix="aqg-blobs-")))
    if deps.registry_builder is None:
        deps.registry_builder = _default_registry_builder
    if deps.keyring is None:
        deps.keyring = InMemoryKeyring()

    app = FastAPI(title="Anchor Quality Gate", version="1.0.0-draft")
    app.state.deps = deps
    app.state.store = deps.store
    app.state.blobs = deps.blobs
    app.state.api_key_resolver = deps.api_key_resolver

    @app.get("/v1/health", response_model=HealthResponse, tags=["meta"])
    async def health() -> HealthResponse:
        return HealthResponse()

    @app.post(
        "/v1/documents",
        response_model=DocumentRef,
        status_code=status.HTTP_201_CREATED,
        tags=["documents"],
    )
    async def upload_document(
        file: UploadFile = File(..., description="docx file"),
        principal: RequestPrincipal = Depends(require_principal),
    ) -> DocumentRef:
        if not file.filename or not file.filename.lower().endswith(".docx"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="upload must be a .docx file",
            )
        contents = await file.read()
        document_id = new_id()
        import hashlib
        sha = hashlib.sha256(contents).hexdigest()

        deps.blobs.put(org_id=principal.org_id, key=f"{document_id}.docx", data=contents)
        deps.store.put_document(
            DocumentRecord(
                id=document_id,
                org_id=principal.org_id,
                sha256=sha,
                original_filename=file.filename,
            )
        )
        return DocumentRef(document_id=document_id)

    @app.post(
        "/v1/documents/encrypted",
        response_model=DocumentRef,
        status_code=status.HTTP_201_CREATED,
        tags=["documents"],
    )
    async def upload_encrypted_document(
        body: EncryptedUploadRequest,
        principal: RequestPrincipal = Depends(require_principal),
    ) -> DocumentRef:
        """Envelope-encrypted upload: server stores ciphertext + nonce +
        wrapped_dek but cannot read plaintext until it unwraps the DEK
        via the keyring at run time."""
        import base64

        if deps.keyring.public_key_pem(principal.org_id) is None:
            raise HTTPException(
                status_code=status.HTTP_412_PRECONDITION_FAILED,
                detail=(
                    "no public key registered for this org; encrypted upload "
                    "requires GET /v1/orgs/me/public-key to return a key first"
                ),
            )

        try:
            ciphertext = base64.b64decode(body.ciphertext_b64, validate=True)
            nonce = base64.b64decode(body.nonce_b64, validate=True)
            wrapped_dek = base64.b64decode(body.wrapped_dek_b64, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"invalid base64 in upload payload: {exc}",
            )

        document_id = new_id()
        deps.blobs.put(
            org_id=principal.org_id,
            key=f"{document_id}.docx.enc",
            data=ciphertext,
        )
        deps.store.put_document(
            DocumentRecord(
                id=document_id,
                org_id=principal.org_id,
                sha256=body.sha256,
                original_filename=body.original_filename,
                encrypted=True,
                wrapped_dek=wrapped_dek,
                nonce=nonce,
            )
        )
        return DocumentRef(document_id=document_id)

    @app.get(
        "/v1/orgs/me/public-key",
        response_model=PublicKeyResponse,
        tags=["orgs"],
    )
    async def get_org_public_key(
        principal: RequestPrincipal = Depends(require_principal),
    ) -> PublicKeyResponse:
        """Return the public key the client should encrypt DEKs against."""
        pem = deps.keyring.public_key_pem(principal.org_id)
        if pem is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="no public key registered for this org",
            )
        return PublicKeyResponse(
            org_id=principal.org_id,
            public_key_pem=pem.decode("ascii"),
        )

    @app.post(
        "/v1/runs",
        response_model=RunRef,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["runs"],
    )
    async def create_run(
        body: CreateRunRequest,
        principal: RequestPrincipal = Depends(require_principal),
    ) -> RunRef:
        doc = deps.store.get_document(body.document_id, principal.org_id)
        if doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="document not found",
            )
        run_id = new_id()
        record = RunRecord(
            id=run_id,
            org_id=principal.org_id,
            document_id=body.document_id,
            policy_id=body.policy_id,
            mode=body.mode,
            status="running",
        )
        deps.store.put_run(record)

        # v1 alpha: synchronous execution. v1.5 dispatches to RQ.
        await _run_pipeline(deps=deps, run=record, doc=doc)

        return RunRef(
            run_id=run_id,
            status_url=f"/v1/runs/{run_id}",
            status=record.status,
        )

    @app.get(
        "/v1/runs/{run_id}",
        response_model=QualityReport,
        tags=["runs"],
    )
    async def get_run(
        run_id: str,
        principal: RequestPrincipal = Depends(require_principal),
    ) -> QualityReport:
        record = deps.store.get_run(run_id, principal.org_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="run not found"
            )
        if record.report is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"run is {record.status}; report not yet available",
            )
        return record.report

    @app.get(
        "/v1/runs/{run_id}/annotated.docx",
        response_class=StreamingResponse,
        tags=["runs"],
    )
    async def download_annotated(
        run_id: str,
        principal: RequestPrincipal = Depends(require_principal),
    ) -> StreamingResponse:
        record = deps.store.get_run(run_id, principal.org_id)
        if record is None or not record.annotated_blob_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="annotated docx not available",
            )
        data = deps.blobs.get(org_id=principal.org_id, key=record.annotated_blob_key)
        return StreamingResponse(
            io.BytesIO(data),
            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )

    return app


# -------- Registry composition --------

def _default_registry_builder(
    rules: dict | None = None,
    *,
    llm_client=None,
    authority_client=None,
) -> CheckerRegistry:
    """Inline registry composition for the API.

    Deliberately not imported from legal_cli — that would couple the
    SaaS surface to the CLI package. Each entry point composes its own
    registry; the function is small and the small duplication is
    cheaper than the cross-package coupling.
    """
    registry = CheckerRegistry()
    registry.register(build_formatting_checker(rules=rules or {}))
    registry.register(build_signal_checker())
    registry.register(build_pinpoint_checker())
    registry.register(build_short_form_checker())
    if llm_client is not None:
        registry.register(build_case_form_checker(llm=llm_client))
    if authority_client is not None:
        registry.register(build_citations_exists_checker(authority=authority_client))
    return registry


# -------- Pipeline driver --------


async def _run_pipeline(*, deps: AppDeps, run: RunRecord, doc: DocumentRecord) -> None:
    """Decrypt blob (envelope-style if encrypted) → parse → run pipeline
    → (if autofix) write annotated → persist."""
    try:
        if doc.encrypted:
            # Envelope flow: ciphertext blob + wrapped DEK from the
            # document record + nonce. Unwrap the DEK through the
            # keyring (which in production callbacks to the customer's
            # plugin; in v1 alpha and tests holds the private key
            # directly).
            ciphertext = deps.blobs.get(
                org_id=run.org_id, key=f"{run.document_id}.docx.enc"
            )
            assert doc.wrapped_dek is not None
            assert doc.nonce is not None
            dek = deps.keyring.unwrap(
                org_id=run.org_id, wrapped_dek=doc.wrapped_dek
            )
            try:
                plaintext = decrypt_document(ciphertext, doc.nonce, dek)
            finally:
                # Best-effort scrub. CPython doesn't guarantee zeroing
                # but at least the reference is dropped immediately.
                del dek
        else:
            plaintext = deps.blobs.get(
                org_id=run.org_id, key=f"{run.document_id}.docx"
            )

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp.write(plaintext)
            tmp_path = Path(tmp.name)
        del plaintext  # drop the reference promptly

        result = parse_docx(tmp_path, document_id=run.document_id)
        policy = deps.policy_loader(run.policy_id) if (
            deps.policy_loader and run.policy_id
        ) else Policy()
        registry = deps.registry_builder(
            rules={},
            llm_client=deps.llm_client,
            authority_client=deps.authority_client,
        )
        ctx = CheckContext(text_loader=result.text_loader)
        report = await Pipeline(registry, policy=policy).run(result.document, ctx)

        annotated_key: str | None = None
        if run.mode == "autofix":
            safe = [
                f.suggestion for f in report.findings
                if f.suggestion is not None and f.suggestion.auto_apply_safe
            ]
            if safe:
                out_path = tmp_path.with_suffix(".fixed.docx")
                write_annotated(
                    original_path=tmp_path,
                    suggestions=safe,
                    out_path=out_path,
                    segment_ordinal_by_id=result.segment_ordinal_by_id,
                )
                annotated_key = f"{run.id}.fixed.docx"
                deps.blobs.put(
                    org_id=run.org_id,
                    key=annotated_key,
                    data=out_path.read_bytes(),
                )

        deps.store.update_run(
            run.id, run.org_id,
            status="done",
            report=report,
            annotated_blob_key=annotated_key,
        )
    except Exception:
        deps.store.update_run(run.id, run.org_id, status="failed")
        raise


# -------- Convenience for `uvicorn legal_api.main:app` --------
# Built lazily so importing this module for tests doesn't allocate a
# temp blob dir.

_lazy_app: FastAPI | None = None


def __getattr__(name: str) -> Any:
    global _lazy_app
    if name == "app":
        if _lazy_app is None:
            _lazy_app = create_app()
        return _lazy_app
    raise AttributeError(name)
