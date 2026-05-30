"""Tests for the thresholds YAML loader + check functions."""

from __future__ import annotations

import textwrap
from pathlib import Path

from tools.eval.thresholds import (
    PromptThresholds,
    check_absolute,
    check_regression,
    load_thresholds,
)


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "thresholds.yaml"
    path.write_text(textwrap.dedent(body))
    return path


def test_loads_prompt_with_models_and_regression(tmp_path: Path):
    path = _write(tmp_path, """
        bluebook.normalize_case@v1:
          regression:
            accuracy_pp: 3.0
            cost_pct: 15.0
          models:
            anthropic/claude-haiku-4-5:
              min_accuracy: 0.85
              max_cost_cents_per_call: 5
              max_p95_latency_ms: 2500
    """)
    pts = load_thresholds(path)
    pt = pts["bluebook.normalize_case@v1"]
    assert isinstance(pt, PromptThresholds)
    assert pt.regression.accuracy_pp == 3.0
    assert pt.regression.cost_pct == 15.0
    haiku = pt.models["anthropic/claude-haiku-4-5"]
    assert haiku.min_accuracy == 0.85
    assert haiku.max_cost_cents_per_call == 5


def test_check_absolute_min_accuracy_violation(tmp_path: Path):
    path = _write(tmp_path, """
        p@1:
          models:
            m1:
              min_accuracy: 0.90
              max_cost_cents_per_call: 10
              max_p95_latency_ms: 5000
    """)
    pts = load_thresholds(path)
    out = check_absolute(
        pts["p@1"], model="m1",
        accuracy=0.80, mean_cost_cents=5, p95_latency_ms=1000,
    )
    kinds = {v.kind for v in out}
    assert "min_accuracy" in kinds


def test_check_absolute_cost_violation(tmp_path: Path):
    path = _write(tmp_path, """
        p@1:
          models:
            m1:
              min_accuracy: 0.5
              max_cost_cents_per_call: 5
              max_p95_latency_ms: 5000
    """)
    pts = load_thresholds(path)
    out = check_absolute(
        pts["p@1"], model="m1",
        accuracy=0.9, mean_cost_cents=12, p95_latency_ms=1000,
    )
    assert any(v.kind == "max_cost_cents_per_call" for v in out)


def test_check_absolute_latency_violation(tmp_path: Path):
    path = _write(tmp_path, """
        p@1:
          models:
            m1:
              min_accuracy: 0.5
              max_cost_cents_per_call: 100
              max_p95_latency_ms: 1000
    """)
    pts = load_thresholds(path)
    out = check_absolute(
        pts["p@1"], model="m1",
        accuracy=0.9, mean_cost_cents=10, p95_latency_ms=5000,
    )
    assert any(v.kind == "max_p95_latency_ms" for v in out)


def test_check_absolute_no_threshold_for_model_returns_empty(tmp_path: Path):
    path = _write(tmp_path, """
        p@1:
          models:
            m1: {min_accuracy: 0.5, max_cost_cents_per_call: 100, max_p95_latency_ms: 1000}
    """)
    pts = load_thresholds(path)
    out = check_absolute(
        pts["p@1"], model="m2",  # unknown
        accuracy=0.0, mean_cost_cents=999, p95_latency_ms=999_999,
    )
    assert out == []


def test_check_regression_accuracy_drop(tmp_path: Path):
    path = _write(tmp_path, """
        p@1:
          regression:
            accuracy_pp: 2.0
          models: {m1: {min_accuracy: 0, max_cost_cents_per_call: 1e9, max_p95_latency_ms: 1e9}}
    """)
    pts = load_thresholds(path)
    out = check_regression(
        pts["p@1"], model="m1",
        current_accuracy=0.80, baseline_accuracy=0.85,  # 5pp drop
        current_mean_cost_cents=5, baseline_mean_cost_cents=5,
        current_p95_ms=1000, baseline_p95_ms=1000,
    )
    assert any(v.kind == "regression.accuracy_pp" for v in out)


def test_check_regression_cost_rise(tmp_path: Path):
    path = _write(tmp_path, """
        p@1:
          regression:
            cost_pct: 10.0
          models: {m1: {min_accuracy: 0, max_cost_cents_per_call: 1e9, max_p95_latency_ms: 1e9}}
    """)
    pts = load_thresholds(path)
    out = check_regression(
        pts["p@1"], model="m1",
        current_accuracy=0.9, baseline_accuracy=0.9,
        current_mean_cost_cents=12, baseline_mean_cost_cents=10,  # +20%
        current_p95_ms=1000, baseline_p95_ms=1000,
    )
    assert any(v.kind == "regression.cost_pct" for v in out)


def test_check_regression_under_thresholds_returns_empty(tmp_path: Path):
    path = _write(tmp_path, """
        p@1:
          regression: {accuracy_pp: 5, cost_pct: 50, latency_pct: 100}
          models: {m1: {min_accuracy: 0, max_cost_cents_per_call: 1e9, max_p95_latency_ms: 1e9}}
    """)
    pts = load_thresholds(path)
    out = check_regression(
        pts["p@1"], model="m1",
        current_accuracy=0.92, baseline_accuracy=0.93,  # tiny drop
        current_mean_cost_cents=5, baseline_mean_cost_cents=5,
        current_p95_ms=1100, baseline_p95_ms=1000,
    )
    assert out == []
