"""Deterministic, schema-aware scorers.

These run first and gate the more expensive (LLM-judge) scorers. They
return 0 or 1 (boolean correctness) or — for FieldMatch — a real value
in [0, 1] (fraction of fields matched).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from tools.eval.scorers.base import ScoreResult


@dataclass
class SchemaValid:
    """1.0 iff `candidate is not None` (the runner already validated it
    against the Pydantic output_schema before populating)."""

    name: str = "schema_valid"

    def score(
        self,
        *,
        candidate: dict[str, Any] | None,
        gold: dict[str, Any],
        case_input: dict[str, Any],
    ) -> ScoreResult:
        return ScoreResult(self.name, 1.0 if candidate is not None else 0.0)


@dataclass
class ExactMatch:
    """1.0 iff `candidate[field] == gold[field]` (string compared after
    `str()`; useful for canonical-form scoring).
    """

    field: str = "canonical"
    name: str = "exact_match"

    def score(
        self,
        *,
        candidate: dict[str, Any] | None,
        gold: dict[str, Any],
        case_input: dict[str, Any],
    ) -> ScoreResult:
        if candidate is None:
            return ScoreResult(self.name, 0.0, {"reason": "no candidate"})
        c = str(candidate.get(self.field, ""))
        g = str(gold.get(self.field, ""))
        return ScoreResult(
            self.name,
            1.0 if c == g else 0.0,
            {"candidate": c, "gold": g},
        )


@dataclass
class FieldMatch:
    """Fraction of named fields where candidate == gold.

    Skips fields where gold is missing or None (those are unscoreable).
    """

    fields: Iterable[str] = ()
    name: str = "field_match"

    def score(
        self,
        *,
        candidate: dict[str, Any] | None,
        gold: dict[str, Any],
        case_input: dict[str, Any],
    ) -> ScoreResult:
        if candidate is None:
            return ScoreResult(self.name, 0.0, {"reason": "no candidate"})
        scoreable: list[str] = []
        matches: list[str] = []
        per_field: dict[str, bool] = {}
        for f in self.fields:
            g = gold.get(f)
            if g is None or g == "":
                continue
            scoreable.append(f)
            c = candidate.get(f)
            ok = c == g
            per_field[f] = ok
            if ok:
                matches.append(f)
        if not scoreable:
            return ScoreResult(self.name, 1.0, {"reason": "no scoreable fields"})
        return ScoreResult(
            self.name,
            len(matches) / len(scoreable),
            {"per_field": per_field, "scoreable": scoreable},
        )
