"""Reliability-diagram (calibration) computation.

When the LLM returns `confidence=0.9`, is it correct 90% of the time?
We answer that by binning case results by stated confidence, measuring
actual accuracy per bin, and computing the Expected Calibration Error
(ECE) — the weighted average gap between confidence and accuracy.

Below ~0.05 ECE we consider the model well-calibrated; above 0.10 the
confidence outputs are not safe to use as a gate. Our
`BluebookCaseFormChecker` gates findings at `min_confidence=0.7`, so
calibration drift here directly changes false-positive rates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from tools.eval.types import CaseResult


_DEFAULT_BUCKETS = (
    (0.0, 0.1),
    (0.1, 0.2),
    (0.2, 0.3),
    (0.3, 0.4),
    (0.4, 0.5),
    (0.5, 0.6),
    (0.6, 0.7),
    (0.7, 0.8),
    (0.8, 0.9),
    (0.9, 1.0001),  # include 1.0
)


@dataclass(frozen=True)
class CalibrationBucket:
    lo: float
    hi: float
    count: int
    mean_confidence: float
    accuracy: float


@dataclass(frozen=True)
class CalibrationReport:
    buckets: tuple[CalibrationBucket, ...]
    ece: float  # Expected Calibration Error
    n_scored: int

    def well_calibrated(self, threshold: float = 0.05) -> bool:
        return self.ece <= threshold


def compute_calibration(
    results: Iterable[CaseResult],
    *,
    correctness_scorer: str = "bluebook_fuzzy",
    buckets: Iterable[tuple[float, float]] = _DEFAULT_BUCKETS,
) -> CalibrationReport:
    """Bucket results by stated confidence, compute per-bucket accuracy."""
    bucket_rows: dict[tuple[float, float], list[CaseResult]] = {
        b: [] for b in buckets
    }
    n_with_confidence = 0
    for cr in results:
        if cr.confidence is None:
            continue
        if cr.scores.get(correctness_scorer) is None:
            continue
        n_with_confidence += 1
        for lo, hi in bucket_rows:
            if lo <= cr.confidence < hi:
                bucket_rows[(lo, hi)].append(cr)
                break

    out_buckets: list[CalibrationBucket] = []
    ece = 0.0
    for (lo, hi), rows in bucket_rows.items():
        if not rows:
            out_buckets.append(CalibrationBucket(lo, hi, 0, 0.0, 0.0))
            continue
        mean_conf = sum(cr.confidence or 0.0 for cr in rows) / len(rows)
        acc = sum(
            1.0 if (cr.scores.get(correctness_scorer) or 0.0) >= 1.0 else 0.0
            for cr in rows
        ) / len(rows)
        out_buckets.append(
            CalibrationBucket(lo, hi, len(rows), mean_conf, acc)
        )
        # ECE weight = bucket population / total population.
        if n_with_confidence:
            ece += abs(mean_conf - acc) * (len(rows) / n_with_confidence)

    return CalibrationReport(
        buckets=tuple(out_buckets),
        ece=ece,
        n_scored=n_with_confidence,
    )
