"""Persistence interface for documents, runs, and findings.

v1 alpha ships an in-memory store; v1.5 swaps a Postgres-backed
implementation behind the same Protocol. Anything stored here is
metadata only — encrypted document bytes live in the blob store
(`legal_api.blobs`).

The Protocol intentionally mirrors the shape of the FastAPI requests
and responses so wiring the Postgres implementation later is a matter
of changing the constructor in `main.py`.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from legal_quality_gate import QualityReport


@dataclass
class DocumentRecord:
    id: str
    org_id: str
    sha256: str
    original_filename: str | None = None
    encrypted: bool = False
    # Set when `encrypted=True`. The wrapped_dek + nonce travel with
    # the metadata; the ciphertext sits in the blob store.
    wrapped_dek: bytes | None = None
    nonce: bytes | None = None


@dataclass
class RunRecord:
    id: str
    org_id: str
    document_id: str
    policy_id: str | None
    mode: str  # "report" | "autofix"
    status: str = "queued"  # queued | running | done | failed
    report: QualityReport | None = None
    annotated_blob_key: str | None = None


class Store(Protocol):
    def put_document(self, record: DocumentRecord) -> None: ...
    def get_document(self, document_id: str, org_id: str) -> DocumentRecord | None: ...

    def put_run(self, record: RunRecord) -> None: ...
    def get_run(self, run_id: str, org_id: str) -> RunRecord | None: ...
    def update_run(
        self,
        run_id: str,
        org_id: str,
        *,
        status: str | None = None,
        report: QualityReport | None = None,
        annotated_blob_key: str | None = None,
    ) -> RunRecord: ...


@dataclass
class InMemoryStore:
    """Thread-safe in-memory implementation.

    v1 alpha and tests use this; production swaps a Postgres impl.
    """

    documents: dict[tuple[str, str], DocumentRecord] = field(default_factory=dict)
    runs: dict[tuple[str, str], RunRecord] = field(default_factory=dict)
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def put_document(self, record: DocumentRecord) -> None:
        with self._lock:
            self.documents[(record.org_id, record.id)] = record

    def get_document(
        self, document_id: str, org_id: str
    ) -> DocumentRecord | None:
        with self._lock:
            return self.documents.get((org_id, document_id))

    def put_run(self, record: RunRecord) -> None:
        with self._lock:
            self.runs[(record.org_id, record.id)] = record

    def get_run(self, run_id: str, org_id: str) -> RunRecord | None:
        with self._lock:
            return self.runs.get((org_id, run_id))

    def update_run(
        self,
        run_id: str,
        org_id: str,
        *,
        status: str | None = None,
        report: QualityReport | None = None,
        annotated_blob_key: str | None = None,
    ) -> RunRecord:
        with self._lock:
            record = self.runs[(org_id, run_id)]
            if status is not None:
                record.status = status
            if report is not None:
                record.report = report
            if annotated_blob_key is not None:
                record.annotated_blob_key = annotated_blob_key
            return record


def new_id() -> str:
    return str(uuid.uuid4())
