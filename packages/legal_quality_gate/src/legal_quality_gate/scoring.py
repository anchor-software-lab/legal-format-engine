"""Scoring + finding dedup.

The Pipeline calls `score_findings()` after all checkers have produced
their findings. Default scoring is conservative: every error costs 10
points, warning costs 3, info costs 1, capped at 100 loss.
"""

from __future__ import annotations

from legal_quality_gate.types import Finding, Severity

_WEIGHTS = {Severity.ERROR: 10.0, Severity.WARNING: 3.0, Severity.INFO: 1.0}


def score_findings(findings: list[Finding], *, base: float = 100.0) -> float:
    loss = sum(_WEIGHTS[f.severity] for f in findings)
    return max(0.0, base - min(loss, base))


def dedupe(findings: list[Finding]) -> list[Finding]:
    """Drop exact duplicates by (segment_id, rule_id, message)."""
    seen: set[tuple[str, str, str]] = set()
    out: list[Finding] = []
    for f in findings:
        key = (f.segment_id, f.rule_id, f.message)
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out
