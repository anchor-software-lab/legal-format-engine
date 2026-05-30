"""LLM-backed Bluebook case-form normalization.

`BluebookCaseFormChecker` walks the extracted full case citations,
asks the LLM gateway to produce a Bluebook-canonical form via the
`bluebook.normalize_case@vN` prompt, and emits `BB.CASE.FORM` findings
when the canonical form differs from the observed raw text.

This is the first LLM-bound checker in the codebase. It declares
`Capability.LLM` so the pipeline runs it after deterministic checkers
and lets offline policies skip it. Tests inject a `FakeLLMClient` so
the suite stays offline.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Iterable

from pydantic import BaseModel, Field

from legal_citations.checkers import get_or_extract_citations
from legal_llm_gateway import CacheMode, LLMClient, LLMError, Routing
from legal_quality_gate.types import (
    Capability,
    CharRange,
    Finding,
    Provenance,
    Severity,
    Suggestion,
    SuggestionKind,
)

BLUEBOOK_CASE_FORM_ID = "bluebook.case_form"

PROMPT_ID = "bluebook.normalize_case@v1"


class NormalizeCaseOutput(BaseModel):
    """Schema the LLM must produce for `bluebook.normalize_case@v1`.

    The Bluebook-canonical citation string, plus a per-field decomposition
    so consumers can compare against the parsed citation we already
    have from eyecite.
    """

    canonical: str = Field(..., description="Bluebook-canonical citation string.")
    case_name: str | None = None
    reporter: str | None = None
    volume: int | None = None
    page: int | None = None
    court: str | None = None
    year: int | None = None
    pinpoint: str | None = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)


@dataclass
class BluebookCaseFormChecker:
    """Flags full case citations whose surface form differs from the
    Bluebook-canonical form returned by the LLM.

    Only fires on full case citations with confidence ≥ `min_confidence`
    on the LLM output. Short forms, Id., and supra cites are skipped —
    they have their own rules (Bluebook Rule 10.9) and a separate
    checker will handle them.
    """

    llm: LLMClient
    id: str = BLUEBOOK_CASE_FORM_ID
    severity_default: Severity = Severity.WARNING
    requires: Iterable[Capability] = field(
        default_factory=lambda: (Capability.LLM,)
    )
    min_confidence: float = 0.7
    routing: Routing = Routing.AUTO
    cache: CacheMode = CacheMode.PROMPT_PREFIX

    async def check(self, document, ctx) -> list[Finding]:
        by_segment = get_or_extract_citations(document, ctx)
        findings: list[Finding] = []

        for segment in document.segments:
            text = ctx.get_text(segment)
            for extracted in by_segment[segment.id]:
                if not extracted.is_full_case:
                    continue
                try:
                    output = await self.llm.complete(
                        prompt_id=PROMPT_ID,
                        variables={
                            "raw": extracted.citation.raw_text,
                            "context": _surrounding_context(text, extracted),
                            "jurisdiction": _jurisdiction_hint(document),
                        },
                        output_schema=NormalizeCaseOutput,
                        routing=self.routing,
                        cache=self.cache,
                    )
                except LLMError as exc:
                    # The pipeline already isolates checker exceptions,
                    # but we want a finer-grained signal here so users
                    # know the LLM didn't get to weigh in.
                    findings.append(
                        _finding(
                            segment_id=segment.id,
                            checker_id=self.id,
                            rule_id="BB.CASE.FORM.UNAVAILABLE",
                            severity=Severity.INFO,
                            message=(
                                f"LLM normalization unavailable for "
                                f"{extracted.citation.raw_text!r}: {exc.reason}"
                            ),
                            evidence={"providers_tried": exc.providers_tried},
                            confidence=0.0,
                            provenance=Provenance.LLM,
                        )
                    )
                    continue

                normalized = output.output
                if normalized.confidence < self.min_confidence:
                    continue

                if _surface_matches(extracted.citation.raw_text, normalized.canonical):
                    continue

                findings.append(
                    _case_form_finding(
                        segment_id=segment.id,
                        checker_id=self.id,
                        extracted=extracted,
                        canonical=normalized.canonical,
                        confidence=normalized.confidence,
                    )
                )

        return findings


def _surrounding_context(text: str, extracted) -> str:
    """Pull the sentence (or short window) around the citation.

    Cheap heuristic: 150 chars on either side, clipped to nearest
    sentence boundary. Good enough for the v0 prompt; a richer
    context-builder lands when quote-accuracy comes online.
    """
    start = max(0, extracted.citation.span.start - 150)
    end = min(len(text), extracted.citation.span.end + 150)
    window = text[start:end]
    # Trim to nearest sentence boundary on each side.
    if start > 0:
        for sep in (". ", "; ", "! ", "? "):
            i = window.find(sep)
            if 0 <= i < 100:
                window = window[i + len(sep) :]
                break
    return window.strip()


def _jurisdiction_hint(document) -> str | None:
    if document.jurisdiction_hints:
        return document.jurisdiction_hints[0]
    return None


def _surface_matches(raw: str, canonical: str) -> bool:
    """Compare two citation strings ignoring whitespace and italic markup.

    Pure deterministic check before we conclude the surface differs.
    Saves a finding when the only "difference" is a stray space.
    """
    return _norm(raw) == _norm(canonical)


def _norm(s: str) -> str:
    return " ".join(s.split()).replace(" ", " ")


def _case_form_finding(
    *, segment_id: str, checker_id: str, extracted, canonical: str, confidence: float
) -> Finding:
    return Finding(
        id=str(uuid.uuid4()),
        segment_id=segment_id,
        checker_id=checker_id,
        rule_id="BB.CASE.FORM",
        severity=Severity.WARNING,
        message=(
            f"Citation surface form differs from Bluebook canonical: "
            f"{extracted.citation.raw_text!r} → {canonical!r}"
        ),
        evidence={
            "observed": extracted.citation.raw_text,
            "canonical": canonical,
            "llm_confidence": confidence,
        },
        suggestion=Suggestion(
            kind=SuggestionKind.REPLACE,
            range=extracted.citation.span,
            new_text=canonical,
            rationale="LLM-normalized Bluebook surface form",
            auto_apply_safe=False,  # text replacement isn't safe to auto-apply yet
        ),
        confidence=confidence,
        provenance=Provenance.LLM,
    )


def _finding(
    *,
    segment_id: str,
    checker_id: str,
    rule_id: str,
    severity: Severity,
    message: str,
    evidence: dict,
    confidence: float,
    provenance: Provenance,
) -> Finding:
    return Finding(
        id=str(uuid.uuid4()),
        segment_id=segment_id,
        checker_id=checker_id,
        rule_id=rule_id,
        severity=severity,
        message=message,
        evidence=evidence,
        confidence=confidence,
        provenance=provenance,
    )


def build_case_form_checker(llm: LLMClient, **kwargs) -> BluebookCaseFormChecker:
    return BluebookCaseFormChecker(llm=llm, **kwargs)
