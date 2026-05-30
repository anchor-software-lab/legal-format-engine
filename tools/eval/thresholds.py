"""Per-prompt × per-model threshold loader + CI check.

`thresholds.yaml` shape:

    bluebook.normalize_case@v1:
      anthropic/claude-haiku-4-5:
        min_accuracy: 0.85
        max_cost_cents_per_call: 5
        max_p95_latency_ms: 2500
      anthropic/claude-sonnet-4-6:
        min_accuracy: 0.92
        ...

Regression rules (relative-to-previous-run, PR check):
    - accuracy may not drop by more than `regression.accuracy_pp` (pp)
    - cost may not rise by more than `regression.cost_pct` (percent)
    - p95 latency may not rise by more than `regression.latency_pct`
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ModelThreshold:
    model: str
    min_accuracy: float = 0.0
    max_cost_cents_per_call: float = 1_000_000
    max_p95_latency_ms: int = 1_000_000
    accuracy_scorer: str = "bluebook_fuzzy"


@dataclass(frozen=True)
class RegressionPolicy:
    accuracy_pp: float = 2.0  # max allowed drop in percentage points
    cost_pct: float = 10.0    # max allowed rise in percent
    latency_pct: float = 25.0


@dataclass
class PromptThresholds:
    prompt_id: str
    models: dict[str, ModelThreshold] = field(default_factory=dict)
    regression: RegressionPolicy = field(default_factory=RegressionPolicy)


@dataclass
class ThresholdViolation:
    prompt_id: str
    model: str
    kind: str  # "min_accuracy" | "max_cost_cents_per_call" | ...
    observed: float
    threshold: float
    detail: str = ""


def load_thresholds(path: str | Path) -> dict[str, PromptThresholds]:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    return {
        prompt_id: _parse_prompt(prompt_id, body)
        for prompt_id, body in raw.items()
    }


def _coerce_num(v: Any, *, as_int: bool = False) -> float | int:
    """YAML doesn't recognize bare `1e9` as a number — only `1.0e9` —
    so be lenient and accept either."""
    if isinstance(v, (int, float)):
        return int(v) if as_int else float(v)
    f = float(str(v))
    return int(f) if as_int else f


def _parse_prompt(prompt_id: str, body: dict[str, Any]) -> PromptThresholds:
    models: dict[str, ModelThreshold] = {}
    for model, cfg in (body.get("models") or {}).items():
        models[model] = ModelThreshold(
            model=model,
            min_accuracy=_coerce_num(cfg.get("min_accuracy", 0.0)),
            max_cost_cents_per_call=_coerce_num(cfg.get("max_cost_cents_per_call", 1e6)),
            max_p95_latency_ms=_coerce_num(
                cfg.get("max_p95_latency_ms", 1_000_000), as_int=True
            ),
            accuracy_scorer=str(cfg.get("accuracy_scorer", "bluebook_fuzzy")),
        )
    reg_cfg = body.get("regression") or {}
    regression = RegressionPolicy(
        accuracy_pp=float(reg_cfg.get("accuracy_pp", 2.0)),
        cost_pct=float(reg_cfg.get("cost_pct", 10.0)),
        latency_pct=float(reg_cfg.get("latency_pct", 25.0)),
    )
    return PromptThresholds(
        prompt_id=prompt_id,
        models=models,
        regression=regression,
    )


def check_absolute(
    thresholds: PromptThresholds,
    *,
    model: str,
    accuracy: float,
    mean_cost_cents: float,
    p95_latency_ms: int,
) -> list[ThresholdViolation]:
    """Check an absolute threshold (run vs `thresholds.yaml`)."""
    out: list[ThresholdViolation] = []
    mt = thresholds.models.get(model)
    if mt is None:
        return out
    if accuracy < mt.min_accuracy:
        out.append(
            ThresholdViolation(
                prompt_id=thresholds.prompt_id,
                model=model,
                kind="min_accuracy",
                observed=accuracy,
                threshold=mt.min_accuracy,
                detail=f"{accuracy:.3f} < {mt.min_accuracy:.3f}",
            )
        )
    if mean_cost_cents > mt.max_cost_cents_per_call:
        out.append(
            ThresholdViolation(
                prompt_id=thresholds.prompt_id,
                model=model,
                kind="max_cost_cents_per_call",
                observed=mean_cost_cents,
                threshold=mt.max_cost_cents_per_call,
                detail=f"{mean_cost_cents:.2f}¢ > {mt.max_cost_cents_per_call:.2f}¢",
            )
        )
    if p95_latency_ms > mt.max_p95_latency_ms:
        out.append(
            ThresholdViolation(
                prompt_id=thresholds.prompt_id,
                model=model,
                kind="max_p95_latency_ms",
                observed=p95_latency_ms,
                threshold=mt.max_p95_latency_ms,
                detail=f"{p95_latency_ms}ms > {mt.max_p95_latency_ms}ms",
            )
        )
    return out


def check_regression(
    thresholds: PromptThresholds,
    *,
    model: str,
    current_accuracy: float,
    baseline_accuracy: float,
    current_mean_cost_cents: float,
    baseline_mean_cost_cents: float,
    current_p95_ms: int,
    baseline_p95_ms: int,
) -> list[ThresholdViolation]:
    """Check a relative regression (current run vs baseline run)."""
    out: list[ThresholdViolation] = []
    p = thresholds.regression
    acc_drop_pp = (baseline_accuracy - current_accuracy) * 100
    if acc_drop_pp > p.accuracy_pp:
        out.append(
            ThresholdViolation(
                prompt_id=thresholds.prompt_id,
                model=model,
                kind="regression.accuracy_pp",
                observed=acc_drop_pp,
                threshold=p.accuracy_pp,
                detail=f"-{acc_drop_pp:.2f}pp (allowed: -{p.accuracy_pp}pp)",
            )
        )
    if baseline_mean_cost_cents > 0:
        cost_rise_pct = (
            (current_mean_cost_cents - baseline_mean_cost_cents)
            / baseline_mean_cost_cents
            * 100
        )
        if cost_rise_pct > p.cost_pct:
            out.append(
                ThresholdViolation(
                    prompt_id=thresholds.prompt_id,
                    model=model,
                    kind="regression.cost_pct",
                    observed=cost_rise_pct,
                    threshold=p.cost_pct,
                    detail=f"+{cost_rise_pct:.1f}% (allowed: +{p.cost_pct}%)",
                )
            )
    if baseline_p95_ms > 0:
        lat_rise_pct = (
            (current_p95_ms - baseline_p95_ms) / baseline_p95_ms * 100
        )
        if lat_rise_pct > p.latency_pct:
            out.append(
                ThresholdViolation(
                    prompt_id=thresholds.prompt_id,
                    model=model,
                    kind="regression.latency_pct",
                    observed=lat_rise_pct,
                    threshold=p.latency_pct,
                    detail=f"+{lat_rise_pct:.1f}% (allowed: +{p.latency_pct}%)",
                )
            )
    return out
