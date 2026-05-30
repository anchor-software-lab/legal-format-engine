"""Response cache for the eval runner.

Key = SHA-256 of (prompt_id, model, sorted_input_json). Value =
the cached LLMResult-equivalent JSON (raw_output, usage, latency,
cached=True flag).

Purpose:
- Dev loops are free after the first call.
- PR CI only re-runs the cases whose prompt template or input changed.
- Nightly cross-model runs amortize: stable models get cached hits;
  newly added models do real calls.

Backed by a filesystem directory of small JSON files. Atomic via
write-and-rename. No network, no DB; deliberately boring.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CacheKey:
    prompt_id: str
    model: str
    input: dict[str, Any]

    def digest(self) -> str:
        canonical = json.dumps(
            {
                "prompt_id": self.prompt_id,
                "model": self.model,
                "input": self.input,
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


@dataclass
class CachedResponse:
    raw_output: dict[str, Any]
    parsed_output: dict[str, Any] | None
    input_tokens: int
    output_tokens: int
    cost_cents: int
    latency_ms: int


class ResponseCache:
    """Filesystem-backed cache. Construct with a root directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: CacheKey) -> Path:
        digest = key.digest()
        # Two-level fan-out so directory listings stay sane.
        return self.root / digest[:2] / f"{digest}.json"

    def get(self, key: CacheKey) -> CachedResponse | None:
        path = self._path_for(key)
        if not path.exists():
            return None
        with open(path) as f:
            data = json.load(f)
        return CachedResponse(**data)

    def put(self, key: CacheKey, value: CachedResponse) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: tmp file in same dir, then rename.
        fd, tmp = tempfile.mkstemp(
            prefix=".tmp-", suffix=".json", dir=str(path.parent)
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(
                    {
                        "raw_output": value.raw_output,
                        "parsed_output": value.parsed_output,
                        "input_tokens": value.input_tokens,
                        "output_tokens": value.output_tokens,
                        "cost_cents": value.cost_cents,
                        "latency_ms": value.latency_ms,
                    },
                    f,
                )
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    def clear(self) -> int:
        """Delete every cached response. Returns the count removed."""
        count = 0
        for p in self.root.glob("**/*.json"):
            p.unlink()
            count += 1
        return count

    def size(self) -> int:
        return sum(1 for _ in self.root.glob("**/*.json"))


class NullCache:
    """No-op cache; useful when you want force-fresh calls."""

    def get(self, key: CacheKey) -> CachedResponse | None:
        return None

    def put(self, key: CacheKey, value: CachedResponse) -> None:
        return None

    def clear(self) -> int:
        return 0

    def size(self) -> int:
        return 0
