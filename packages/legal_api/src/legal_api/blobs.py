"""Encrypted blob storage interface.

v1 alpha keeps blobs on the filesystem (one directory per org). v1.5
swaps in an S3 / R2 implementation behind the same Protocol.

A "blob" here is opaque — typically the encrypted docx ciphertext, but
also annotated docx outputs after `lqg fix`. The store never decrypts;
encryption / decryption happens at the API boundary or, for the
envelope flow, inside the client.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class BlobStore(Protocol):
    def put(self, *, org_id: str, key: str, data: bytes) -> None: ...
    def get(self, *, org_id: str, key: str) -> bytes: ...
    def exists(self, *, org_id: str, key: str) -> bool: ...


@dataclass
class FilesystemBlobStore:
    """One directory per org under `root`. Keys become filenames."""

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, org_id: str, key: str) -> Path:
        # Defensive: forbid path traversal in keys.
        if "/" in key or ".." in key:
            raise ValueError(f"invalid blob key: {key!r}")
        org_dir = self.root / org_id
        org_dir.mkdir(parents=True, exist_ok=True)
        return org_dir / key

    def put(self, *, org_id: str, key: str, data: bytes) -> None:
        path = self._path(org_id, key)
        path.write_bytes(data)

    def get(self, *, org_id: str, key: str) -> bytes:
        return self._path(org_id, key).read_bytes()

    def exists(self, *, org_id: str, key: str) -> bool:
        return self._path(org_id, key).exists()
