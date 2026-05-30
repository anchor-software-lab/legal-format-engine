"""JSONL dataset loader for the eval harness.

A dataset is one .jsonl file; one EvalCase per line. The format is
intentionally hand-editable so eval cases land in PRs alongside the
code they cover.

Schema (matches `EvalCase`):

    {
      "id": "neutral_cite_wi_001",
      "input": {"raw": "Tews v NHI LLC 2010 WI 137", "context": "...", "jurisdiction": "WI"},
      "expected": {"canonical": "Tews v. NHI, LLC, 2010 WI 137", ...},
      "tags": ["wi", "neutral_cite"],
      "difficulty": "easy",
      "source": "human"
    }
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path

from tools.eval.types import EvalCase


def load_dataset(path: str | Path) -> list[EvalCase]:
    """Load every case from a JSONL file. Raises on malformed records."""
    path = Path(path)
    cases: list[EvalCase] = []
    with open(path) as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            cases.append(_case_from_dict(raw, path, lineno))
    return cases


def iter_dataset(path: str | Path) -> Iterator[EvalCase]:
    """Stream a dataset one case at a time (avoid loading into memory)."""
    path = Path(path)
    with open(path) as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            yield _case_from_dict(raw, path, lineno)


def write_dataset(path: str | Path, cases: Iterable[EvalCase]) -> Path:
    """Write cases out as JSONL, one per line. Returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for case in cases:
            f.write(json.dumps(_case_to_dict(case), ensure_ascii=False) + "\n")
    return path


def _case_from_dict(raw: dict, path: Path, lineno: int) -> EvalCase:
    required = ("id", "input", "expected")
    for k in required:
        if k not in raw:
            raise ValueError(f"{path}:{lineno}: missing required field {k!r}")
    return EvalCase(
        id=str(raw["id"]),
        input=dict(raw["input"]),
        expected=dict(raw["expected"]),
        tags=tuple(raw.get("tags") or ()),
        difficulty=str(raw.get("difficulty", "medium")),
        source=str(raw.get("source", "human")),
        metadata=dict(raw.get("metadata") or {}),
    )


def _case_to_dict(case: EvalCase) -> dict:
    return {
        "id": case.id,
        "input": case.input,
        "expected": case.expected,
        "tags": list(case.tags),
        "difficulty": case.difficulty,
        "source": case.source,
        **({"metadata": case.metadata} if case.metadata else {}),
    }
