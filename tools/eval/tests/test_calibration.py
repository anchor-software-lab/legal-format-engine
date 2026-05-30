"""Tests for calibration / reliability-diagram computation."""

from __future__ import annotations

from datetime import datetime, timezone

from tools.eval.calibration import compute_calibration
from tools.eval.types import CaseResult


def _cr(*, confidence: float, correct: bool, model: str = "m1") -> CaseResult:
    return CaseResult(
        case_id=f"c-{confidence}-{correct}",
        prompt_id="p@1",
        model=model,
        confidence=confidence,
        scores={"bluebook_fuzzy": 1.0 if correct else 0.0},
        schema_valid=True,
        ran_at=datetime.now(timezone.utc),
    )


def test_perfectly_calibrated_low_ece():
    # Each bucket: confidence ≈ accuracy.
    results = []
    # 0.9 bucket: 10 cases, 9 correct.
    results.extend([_cr(confidence=0.95, correct=True) for _ in range(9)])
    results.append(_cr(confidence=0.95, correct=False))
    # 0.5 bucket: 10 cases, 5 correct.
    results.extend([_cr(confidence=0.55, correct=True) for _ in range(5)])
    results.extend([_cr(confidence=0.55, correct=False) for _ in range(5)])

    calib = compute_calibration(results)
    assert calib.well_calibrated(threshold=0.05)
    assert calib.ece < 0.05


def test_overconfident_high_ece():
    # 0.9 bucket: 10 cases but only 5 correct (overconfident).
    results = []
    results.extend([_cr(confidence=0.95, correct=True) for _ in range(5)])
    results.extend([_cr(confidence=0.95, correct=False) for _ in range(5)])

    calib = compute_calibration(results)
    assert not calib.well_calibrated(threshold=0.05)
    assert calib.ece > 0.4  # 0.95 stated, 0.5 actual


def test_calibration_skips_cases_with_no_confidence():
    results = [
        _cr(confidence=0.95, correct=True),
        CaseResult(
            case_id="no-conf",
            prompt_id="p@1",
            model="m1",
            confidence=None,
            scores={"bluebook_fuzzy": 0.0},
        ),
    ]
    calib = compute_calibration(results)
    assert calib.n_scored == 1


def test_calibration_empty_results_zero_ece():
    calib = compute_calibration([])
    assert calib.ece == 0.0
    assert calib.n_scored == 0


def test_calibration_bucket_boundaries():
    # Cases at the edge should land in the correct bucket.
    results = [
        _cr(confidence=0.0, correct=False),
        _cr(confidence=0.1, correct=True),  # falls into [0.1, 0.2)
        _cr(confidence=0.95, correct=True),
        _cr(confidence=1.0, correct=True),  # final bucket includes 1.0
    ]
    calib = compute_calibration(results)
    counts = {(b.lo, b.hi): b.count for b in calib.buckets}
    assert counts[(0.0, 0.1)] == 1
    assert counts[(0.1, 0.2)] == 1
    assert counts[(0.9, 1.0001)] == 2
