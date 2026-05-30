"""Quality-gate Checkers for citations.

v0 ships two deterministic checkers:

- `bluebook.signal` — flags introductory signals that don't match T.1.4.
- `bluebook.pinpoint` — flags full case citations that lack a pinpoint.

Both share an extracted-citations cache stored on `CheckContext.cache`
so eyecite runs at most once per segment per run.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Iterable

from legal_citations.bluebook.signal import (
    SIGNALS,
    SignalKind,
    classify_signal_text,
    find_signal_before,
)
from legal_citations.parser import (
    ExtractedCitation,
    extract_citations_in_text,
    is_parallel_continuation,
)
from legal_quality_gate.types import (
    Capability,
    Document,
    Finding,
    Provenance,
    Severity,
)

BLUEBOOK_SIGNAL_ID = "bluebook.signal"
BLUEBOOK_PINPOINT_ID = "bluebook.pinpoint"

_CACHE_KEY = "legal_citations.extracted_by_segment"


def get_or_extract_citations(
    document: Document, ctx
) -> dict[str, list[ExtractedCitation]]:
    """Return a memoized per-segment ExtractedCitation map for this run."""
    cache: dict[str, list[ExtractedCitation]] | None = ctx.cache.get(_CACHE_KEY)
    if cache is not None:
        return cache

    cache = {}
    for segment in document.segments:
        text = ctx.get_text(segment)
        cache[segment.id] = extract_citations_in_text(text, segment_id=segment.id)
    ctx.cache[_CACHE_KEY] = cache
    return cache


@dataclass
class BluebookSignalChecker:
    """Flags signals not in T.1.4 (e.g. "See, also,", "Cf,", "see e.g.")."""

    id: str = BLUEBOOK_SIGNAL_ID
    severity_default: Severity = Severity.WARNING
    requires: Iterable[Capability] = field(default_factory=tuple)

    def check(self, document: Document, ctx) -> list[Finding]:
        by_segment = get_or_extract_citations(document, ctx)
        findings: list[Finding] = []

        for segment in document.segments:
            for extracted in by_segment[segment.id]:
                signal_text = extracted.citation.parsed.signal
                if not signal_text:
                    # No signal at all — allowed in Bluebook (direct support).
                    continue
                if classify_signal_text(signal_text) is not None:
                    continue
                findings.append(
                    _finding(
                        segment_id=segment.id,
                        checker_id=self.id,
                        rule_id="BB.SIGNAL.UNKNOWN",
                        severity=self.severity_default,
                        message=(
                            f"Signal {signal_text!r} is not a Bluebook T.1.4 "
                            f"signal; expected one of: "
                            f"{', '.join(s for s, _ in SIGNALS)}"
                        ),
                        evidence={
                            "signal": signal_text,
                            "citation": extracted.citation.raw_text,
                        },
                    )
                )
        return findings


@dataclass
class PinpointMissingChecker:
    """Flags full case citations that omit a pinpoint cite.

    Rule of thumb (Bluebook Rule 3.2): when a case is cited for a
    proposition stated in a specific part of the opinion, give the page
    or paragraph. A full case cite with no pinpoint usually means
    the writer forgot — or is citing the case generally, which is
    sometimes correct. We surface it as a WARNING, not an ERROR.
    """

    id: str = BLUEBOOK_PINPOINT_ID
    severity_default: Severity = Severity.WARNING
    requires: Iterable[Capability] = field(default_factory=tuple)

    def check(self, document: Document, ctx) -> list[Finding]:
        by_segment = get_or_extract_citations(document, ctx)
        findings: list[Finding] = []

        for segment_id, extracteds in by_segment.items():
            prev: ExtractedCitation | None = None
            for extracted in extracteds:
                if not extracted.is_full_case:
                    prev = extracted
                    continue
                # Parallel cites share the case name. The pinpoint
                # belongs to the lead cite; don't fault each reporter.
                if prev is not None and is_parallel_continuation(prev, extracted):
                    prev = extracted
                    continue
                if extracted.citation.parsed.pinpoint:
                    prev = extracted
                    continue
                findings.append(
                    _finding(
                        segment_id=segment_id,
                        checker_id=self.id,
                        rule_id="BB.PINPOINT.MISSING",
                        severity=self.severity_default,
                        message=(
                            f"Full case citation {extracted.citation.raw_text!r} "
                            f"has no pinpoint; add the page or paragraph cited."
                        ),
                        evidence={"citation": extracted.citation.raw_text},
                    )
                )
                prev = extracted
        return findings


def _finding(
    *,
    segment_id: str,
    checker_id: str,
    rule_id: str,
    severity: Severity,
    message: str,
    evidence: dict,
) -> Finding:
    return Finding(
        id=str(uuid.uuid4()),
        segment_id=segment_id,
        checker_id=checker_id,
        rule_id=rule_id,
        severity=severity,
        message=message,
        evidence=evidence,
        confidence=0.9,
        provenance=Provenance.RULE,
    )


def build_signal_checker(**kwargs) -> BluebookSignalChecker:
    return BluebookSignalChecker(**kwargs)


def build_pinpoint_checker(**kwargs) -> PinpointMissingChecker:
    return PinpointMissingChecker(**kwargs)
