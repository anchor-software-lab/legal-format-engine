"""Domain types for the eval harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class EvalCase:
    """One labeled (input, expected_output) pair from a dataset."""

    id: str
    input: dict[str, Any]
    expected: dict[str, Any]
    tags: tuple[str, ...] = ()
    difficulty: str = "medium"  # easy | medium | hard
    source: str = "human"  # human | synthetic | adversarial
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CaseResult:
    """Outcome of running one EvalCase against one model."""

    case_id: str
    prompt_id: str
    model: str
    raw_output: dict[str, Any] | None = None
    parsed_output: dict[str, Any] | None = None
    schema_valid: bool = False
    scores: dict[str, float] = field(default_factory=dict)
    confidence: float | None = None
    cost_cents: int = 0
    latency_ms: int = 0
    cached: bool = False
    error: str | None = None
    ran_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RunReport:
    """Aggregate of running a dataset across one or more models."""

    run_id: str
    prompt_id: str
    dataset_path: str
    models: list[str]
    case_results: list[CaseResult]
    started_at: datetime
    finished_at: datetime
    config: dict[str, Any] = field(default_factory=dict)

    def per_model(self) -> dict[str, list[CaseResult]]:
        out: dict[str, list[CaseResult]] = {m: [] for m in self.models}
        for cr in self.case_results:
            out.setdefault(cr.model, []).append(cr)
        return out

    def mean_score(self, model: str, scorer: str) -> float:
        rows = [cr.scores.get(scorer) for cr in self.case_results if cr.model == model]
        rows = [r for r in rows if r is not None]
        return sum(rows) / len(rows) if rows else 0.0

    def schema_valid_rate(self, model: str) -> float:
        rows = [cr for cr in self.case_results if cr.model == model]
        return sum(1 for cr in rows if cr.schema_valid) / len(rows) if rows else 0.0

    def mean_cost_cents(self, model: str) -> float:
        rows = [cr.cost_cents for cr in self.case_results if cr.model == model]
        return sum(rows) / len(rows) if rows else 0.0

    def p95_latency_ms(self, model: str) -> int:
        rows = sorted(cr.latency_ms for cr in self.case_results if cr.model == model)
        if not rows:
            return 0
        idx = max(0, int(len(rows) * 0.95) - 1)
        return rows[idx]
