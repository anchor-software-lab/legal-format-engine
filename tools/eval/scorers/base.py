"""Scorer Protocol + ScoreResult."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Protocol, runtime_checkable


@dataclass
class ScoreResult:
    name: str
    value: float  # 0.0 - 1.0
    detail: dict[str, Any] | None = None


@runtime_checkable
class Scorer(Protocol):
    """Compares `(candidate, gold)` for one case and returns a score.

    `name` is used as the column/header. `score` is async so judge
    scorers can call the LLM gateway; programmatic scorers ignore the
    awaitable and return immediately.
    """

    name: str

    def score(
        self,
        *,
        candidate: dict[str, Any] | None,
        gold: dict[str, Any],
        case_input: dict[str, Any],
    ) -> Awaitable[ScoreResult] | ScoreResult: ...
