"""Authority-backed citation checkers.

`CitationExistsChecker`:
- `CITE.GHOST` (ERROR): the citation has no match in the authority
  database — almost certainly hallucinated or mistyped.
- `CITE.GOOD_LAW.QUESTIONED` / `OVERRULED` / `REVERSED` / `VACATED` /
  `SUPERSEDED` (varying severities): the cited authority is no longer
  good law.

Both checks share one authority lookup per citation, results cached on
`CheckContext.cache` so duplicate cites in the document only query once.

Requires `Capability.NETWORK` + `Capability.AUTHORITY_DB`; offline
policies omit it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Iterable

from legal_authority import AuthorityLookupClient
from legal_citations.checkers import get_or_extract_citations
from legal_quality_gate.types import (
    Capability,
    Document,
    Finding,
    GoodLawStatus,
    Provenance,
    Severity,
)

CITATION_EXISTS_ID = "citations.exists"

_CACHE_KEY = "legal_citations.authority_by_raw"


# Map negative-status enums to the rule_id and severity we surface.
_STATUS_TO_RULE: dict[GoodLawStatus, tuple[str, Severity]] = {
    GoodLawStatus.OVERRULED: ("CITE.GOOD_LAW.OVERRULED", Severity.ERROR),
    GoodLawStatus.REVERSED: ("CITE.GOOD_LAW.REVERSED", Severity.ERROR),
    GoodLawStatus.VACATED: ("CITE.GOOD_LAW.VACATED", Severity.ERROR),
    GoodLawStatus.SUPERSEDED: ("CITE.GOOD_LAW.SUPERSEDED", Severity.WARNING),
    GoodLawStatus.QUESTIONED: ("CITE.GOOD_LAW.QUESTIONED", Severity.WARNING),
}


@dataclass
class CitationExistsChecker:
    """Flags ghost cites and not-good-law cites by hitting the authority DB."""

    authority: AuthorityLookupClient
    id: str = CITATION_EXISTS_ID
    severity_default: Severity = Severity.ERROR
    requires: Iterable[Capability] = field(
        default_factory=lambda: (Capability.NETWORK, Capability.AUTHORITY_DB)
    )
    # Suppress findings for citations whose case_name eyecite couldn't
    # parse — those are usually noise from OCR'd text and would
    # produce false-positive ghosts.
    require_case_name: bool = True

    async def check(self, document: Document, ctx) -> list[Finding]:
        by_segment = get_or_extract_citations(document, ctx)
        authority_cache: dict[str, object] = ctx.cache.setdefault(_CACHE_KEY, {})

        findings: list[Finding] = []
        for segment in document.segments:
            for extracted in by_segment[segment.id]:
                if not extracted.is_full_case:
                    continue
                if self.require_case_name and not extracted.citation.parsed.case_name:
                    continue
                raw = extracted.citation.raw_text

                if raw in authority_cache:
                    authority = authority_cache[raw]
                else:
                    jurisdiction = (
                        document.jurisdiction_hints[0]
                        if document.jurisdiction_hints
                        else None
                    )
                    try:
                        authority = await self.authority.lookup(
                            raw_citation=raw, jurisdiction_hint=jurisdiction
                        )
                    except Exception as exc:  # noqa: BLE001
                        # Don't kill the pipeline on a single lookup
                        # failure — emit an INFO finding instead and
                        # move on.
                        findings.append(
                            _finding(
                                segment_id=segment.id,
                                rule_id="CITE.LOOKUP.UNAVAILABLE",
                                severity=Severity.INFO,
                                message=(
                                    f"Authority lookup failed for {raw!r}: "
                                    f"{type(exc).__name__}"
                                ),
                                evidence={"citation": raw, "error": str(exc)},
                                confidence=0.0,
                                provenance=Provenance.RULE,
                            )
                        )
                        continue
                    authority_cache[raw] = authority

                if authority is None:
                    findings.append(
                        _finding(
                            segment_id=segment.id,
                            rule_id="CITE.GHOST",
                            severity=Severity.ERROR,
                            message=(
                                f"Citation {raw!r} did not match any "
                                f"authority — likely fabricated or mistyped."
                            ),
                            evidence={
                                "citation": raw,
                                "case_name": extracted.citation.parsed.case_name,
                            },
                            confidence=0.8,
                            provenance=Provenance.RULE,
                        )
                    )
                    continue

                status_rule = _STATUS_TO_RULE.get(authority.current_status)
                if status_rule is not None:
                    rule_id, severity = status_rule
                    findings.append(
                        _finding(
                            segment_id=segment.id,
                            rule_id=rule_id,
                            severity=severity,
                            message=(
                                f"{raw} is no longer good law "
                                f"({authority.current_status.value})."
                            ),
                            evidence={
                                "citation": raw,
                                "authority_id": authority.id,
                                "status": authority.current_status.value,
                                "treatment_count": len(authority.treatments),
                            },
                            confidence=0.85,
                            provenance=Provenance.RULE,
                        )
                    )

        return findings


def _finding(
    *,
    segment_id: str,
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
        checker_id=CITATION_EXISTS_ID,
        rule_id=rule_id,
        severity=severity,
        message=message,
        evidence=evidence,
        confidence=confidence,
        provenance=provenance,
    )


def build_citations_exists_checker(
    authority: AuthorityLookupClient, **kwargs
) -> CitationExistsChecker:
    return CitationExistsChecker(authority=authority, **kwargs)
