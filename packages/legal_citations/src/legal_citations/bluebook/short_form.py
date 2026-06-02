"""Bluebook Rule 10.9 — short-form citation chain validation.

Three deterministic checks:

  BB.SHORT_FORM.ORPHAN_ID
    `Id.` appears with no preceding citation at all.

  BB.SHORT_FORM.INTERVENING
    `Id.` follows a different-case citation, not the one it ostensibly
    refers to. Rule 10.9 binds `Id.` to the immediately preceding
    citation; intervening cites force a switch to a short form.

  BB.SHORT_FORM.NO_ANTECEDENT
    A short-form case citation (e.g., `Tews, 2010 WI 137, ¶ 5`) appears
    before that case has been given a full-form long cite.

This walks every full case + short-form + Id. citation in document
order across all segments. Parallel cites of the same case are
treated as one citation (per Rule 10.3) so they don't count as
intervening.

Requires nothing — no LLM, no network. Reuses
`legal_citations.parser.is_parallel_continuation` and the same
extracted-citations cache on `CheckContext.cache` that the signal
and pinpoint checkers populate.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Iterable

from legal_citations.checkers import get_or_extract_citations
from legal_citations.parser import ExtractedCitation, is_parallel_continuation
from legal_quality_gate.types import (
    Capability,
    Document,
    Finding,
    Provenance,
    Severity,
)

BLUEBOOK_SHORT_FORM_ID = "bluebook.short_form"


@dataclass
class BluebookShortFormChecker:
    """Validates Id. / short-form citation chains per Bluebook Rule 10.9."""

    id: str = BLUEBOOK_SHORT_FORM_ID
    severity_default: Severity = Severity.WARNING
    requires: Iterable[Capability] = field(default_factory=tuple)

    def check(self, document: Document, ctx) -> list[Finding]:
        by_segment = get_or_extract_citations(document, ctx)

        # Walk every extracted citation in document order so we can
        # reason about precedence (Id. binds to the previous one).
        ordered: list[tuple[str, ExtractedCitation]] = []
        for segment in document.segments:
            for ec in by_segment[segment.id]:
                ordered.append((segment.id, ec))

        findings: list[Finding] = []
        long_form_cases: set[str] = set()  # case_names with a known long form
        antecedent_idx: int | None = None  # index of the immediately preceding cite

        for idx, (segment_id, ec) in enumerate(ordered):
            kind = ec.eyecite_type

            if ec.is_full_case:
                name = ec.citation.parsed.case_name
                if name:
                    long_form_cases.add(name)
                antecedent_idx = idx
                continue

            if kind == "IdCitation":
                if antecedent_idx is None:
                    findings.append(
                        _finding(
                            segment_id=segment_id,
                            rule_id="BB.SHORT_FORM.ORPHAN_ID",
                            severity=Severity.WARNING,
                            message=(
                                f"`{ec.citation.raw_text}` has no preceding "
                                f"citation — Bluebook Rule 10.9 forbids "
                                f"orphan Id. references."
                            ),
                            evidence={"citation": ec.citation.raw_text},
                        )
                    )
                    continue

                ant_seg_id, ant_ec = ordered[antecedent_idx]
                intervening = _intervening_citations(
                    ordered, antecedent_idx, idx
                )
                if intervening:
                    interloper_names = sorted({
                        e.citation.parsed.case_name or e.citation.raw_text
                        for e in intervening
                    })
                    findings.append(
                        _finding(
                            segment_id=segment_id,
                            rule_id="BB.SHORT_FORM.INTERVENING",
                            severity=Severity.WARNING,
                            message=(
                                f"`{ec.citation.raw_text}` follows "
                                f"{', '.join(interloper_names)} but the "
                                f"intended antecedent appears to be "
                                f"{ant_ec.citation.parsed.case_name!r}. "
                                f"Bluebook Rule 10.9 requires a short form "
                                f"when an intervening cite breaks the chain."
                            ),
                            evidence={
                                "citation": ec.citation.raw_text,
                                "antecedent": ant_ec.citation.parsed.case_name,
                                "intervening": interloper_names,
                            },
                        )
                    )
                antecedent_idx = idx
                continue

            if kind == "ShortCaseCitation":
                name = ec.citation.parsed.case_name
                if name and name not in long_form_cases:
                    findings.append(
                        _finding(
                            segment_id=segment_id,
                            rule_id="BB.SHORT_FORM.NO_ANTECEDENT",
                            severity=Severity.WARNING,
                            message=(
                                f"Short-form citation `{ec.citation.raw_text}` "
                                f"appears before {name!r} has been given a "
                                f"full long-form citation."
                            ),
                            evidence={
                                "citation": ec.citation.raw_text,
                                "case_name": name,
                            },
                        )
                    )
                antecedent_idx = idx
                continue

            # Other citation kinds (SupraCitation, etc.) — let
            # antecedent advance but don't validate (out of scope for v1).
            antecedent_idx = idx

        return findings


def _intervening_citations(
    ordered: list[tuple[str, ExtractedCitation]],
    antecedent_idx: int,
    current_idx: int,
) -> list[ExtractedCitation]:
    """Return any full case cites between antecedent and current that
    are NOT parallel cites of the antecedent.

    Parallel cites of the antecedent (same case_name, in the standard
    "Tews, 2010 WI 137, 330 Wis. 2d 389, 793 N.W.2d 860" pattern) don't
    break the Id. chain per Rule 10.3.
    """
    if antecedent_idx >= current_idx:
        return []
    antecedent_ec = ordered[antecedent_idx][1]
    antecedent_name = antecedent_ec.citation.parsed.case_name
    out: list[ExtractedCitation] = []
    prev = antecedent_ec
    for j in range(antecedent_idx + 1, current_idx):
        ec = ordered[j][1]
        if not ec.is_full_case:
            prev = ec
            continue
        # Parallel cite continuation of the immediate predecessor?
        if is_parallel_continuation(prev, ec):
            prev = ec
            continue
        # Same case name as the antecedent (later in the document but
        # not contiguous) — still counts as a re-cite of the same case,
        # so it doesn't break Id. binding.
        if antecedent_name and ec.citation.parsed.case_name == antecedent_name:
            prev = ec
            continue
        out.append(ec)
        prev = ec
    return out


def _finding(
    *,
    segment_id: str,
    rule_id: str,
    severity: Severity,
    message: str,
    evidence: dict,
) -> Finding:
    return Finding(
        id=str(uuid.uuid4()),
        segment_id=segment_id,
        checker_id=BLUEBOOK_SHORT_FORM_ID,
        rule_id=rule_id,
        severity=severity,
        message=message,
        evidence=evidence,
        confidence=0.9,
        provenance=Provenance.RULE,
    )


def build_short_form_checker(**kwargs) -> BluebookShortFormChecker:
    return BluebookShortFormChecker(**kwargs)
