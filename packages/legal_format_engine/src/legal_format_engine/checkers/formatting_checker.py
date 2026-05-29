"""The `formatting.spec_diff` checker.

Wraps the existing `merge_with_rules` resolver as a `Checker` in the
quality-gate pipeline. The merge already produces a `_provenance` map
saying which value came from rules / ML / defaults; that map is
forwarded onto each Finding's `evidence` so the UI can explain *why*
the expected value is what it is.

The checker:
  1. Resolves the expected style (rules > ML > defaults) once per run.
  2. For every Segment, compares `style_observed` against the resolved
     spec and produces one Finding per differing dimension.
  3. Attaches a Suggestion with `kind=REFORMAT` and the corrected
     style. Suggestions for fields whose expected value came from a
     `rule` are marked `auto_apply_safe=True`; ML-derived expected
     values are not auto-applied (they're learned heuristics, not
     mandates).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Iterable

from legal_format_engine.ml_integration.format_consumer import (
    FormatSpec,
    merge_with_rules,
)
from legal_quality_gate.types import (
    Capability,
    CharRange,
    Finding,
    ObservedStyle,
    Provenance,
    Segment,
    Severity,
    Suggestion,
    SuggestionKind,
)

FORMATTING_SPEC_DIFF_ID = "formatting.spec_diff"

# Mapping from ObservedStyle attribute → merge_with_rules dict key.
# Kept here (not in legal_quality_gate) because the merge keys are an
# implementation detail of legal_format_engine.
_FIELD_MAP: dict[str, tuple[str, str]] = {
    # observed attr: (resolved key, rule_id)
    "font_name": ("font_name", "FORMAT.FONT.NAME"),
    "font_size_pt": ("font_size_pt", "FORMAT.FONT.SIZE"),
    "line_spacing": ("line_spacing", "FORMAT.LINE_SPACING"),
    "indent_inches": ("body_first_line_indent_inches", "FORMAT.INDENT.BODY"),
    "margin_top_inches": ("margin_top_inches", "FORMAT.MARGIN.TOP"),
    "margin_bottom_inches": ("margin_bottom_inches", "FORMAT.MARGIN.BOTTOM"),
    "margin_left_inches": ("margin_left_inches", "FORMAT.MARGIN.LEFT"),
    "margin_right_inches": ("margin_right_inches", "FORMAT.MARGIN.RIGHT"),
}

_PROVENANCE_MAP = {
    "rule": Provenance.RULE,
    "ml_learned": Provenance.ML,
    "default": Provenance.RULE,  # default values are still deterministic rules
}


@dataclass
class FormattingSpecDiffChecker:
    """Checker that diffs observed style against the resolved FormatSpec."""

    rules: dict = field(default_factory=dict)
    ml_spec: FormatSpec | None = None
    defaults: dict | None = None
    id: str = FORMATTING_SPEC_DIFF_ID
    severity_default: Severity = Severity.WARNING
    requires: Iterable[Capability] = field(default_factory=tuple)

    def check(self, document, ctx) -> list[Finding]:
        resolved = ctx.resolved_style or merge_with_rules(
            self.rules, ml_spec=self.ml_spec, defaults=self.defaults
        )
        # Cache for callers (e.g. a downstream summary).
        ctx.resolved_style = resolved
        provenance = resolved.get("_provenance", {})

        findings: list[Finding] = []
        for segment in document.segments:
            findings.extend(self._diff_segment(segment, resolved, provenance))
        return findings

    def _diff_segment(
        self,
        segment: Segment,
        resolved: dict,
        provenance: dict,
    ) -> list[Finding]:
        out: list[Finding] = []
        observed = segment.style_observed
        for attr, (resolved_key, rule_id) in _FIELD_MAP.items():
            observed_val = getattr(observed, attr, None)
            expected_val = resolved.get(resolved_key)
            if observed_val is None or expected_val is None:
                continue
            if _equal(observed_val, expected_val):
                continue

            prov_label = provenance.get(resolved_key, "default")
            severity = (
                Severity.ERROR if prov_label == "rule" else self.severity_default
            )
            corrected = observed.model_copy(update={attr: expected_val})
            out.append(
                Finding(
                    id=str(uuid.uuid4()),
                    segment_id=segment.id,
                    checker_id=self.id,
                    rule_id=rule_id,
                    severity=severity,
                    message=(
                        f"{attr} is {observed_val!r}; expected {expected_val!r} "
                        f"(source: {prov_label})"
                    ),
                    evidence={
                        "observed": observed_val,
                        "expected": expected_val,
                        "source": prov_label,
                    },
                    suggestion=Suggestion(
                        kind=SuggestionKind.REFORMAT,
                        range=CharRange(
                            segment_id=segment.id,
                            start=0,
                            end=segment.char_length,
                        ),
                        new_style=corrected,
                        rationale=f"Apply {resolved_key}={expected_val!r} from {prov_label}",
                        auto_apply_safe=(prov_label == "rule"),
                    ),
                    confidence=1.0 if prov_label == "rule" else 0.7,
                    provenance=_PROVENANCE_MAP.get(prov_label, Provenance.RULE),
                )
            )
        return out


def build_formatting_checker(
    rules: dict | None = None,
    ml_spec: FormatSpec | None = None,
    defaults: dict | None = None,
) -> FormattingSpecDiffChecker:
    """Factory for the formatting checker.

    Convenience wrapper so callers don't import the dataclass directly.
    """
    return FormattingSpecDiffChecker(
        rules=rules or {}, ml_spec=ml_spec, defaults=defaults
    )


def _equal(a: object, b: object) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) < 1e-6
        except (TypeError, ValueError):
            return False
    return a == b
