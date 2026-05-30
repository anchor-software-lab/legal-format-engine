"""Citation extraction.

Wraps `eyecite` for the heavy lifting (it knows reporter abbreviations,
parses pin cites, links short forms to their long forms) and normalizes
the result into `legal_quality_gate.Citation` records with `CharRange`s
anchored to a segment.

This module is pure-text: it doesn't know about docx, segments, or the
quality-gate pipeline. The Checker layer in `legal_citations.checkers`
glues this to Documents and CheckContexts.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Sequence

from eyecite import get_citations
from eyecite.models import (
    CaseCitation,
    FullCaseCitation,
    IdCitation,
    ShortCaseCitation,
    SupraCitation,
)

from legal_citations.bluebook.signal import SignalKind, find_signal_before
from legal_quality_gate.types import CharRange, Citation, ParsedCitation


@dataclass
class ExtractedCitation:
    """An eyecite citation tagged with metadata we care about downstream."""

    citation: Citation
    is_full_case: bool
    is_short_form: bool  # short form OR id/supra back-references
    eyecite_type: str


def extract_citations_in_text(text: str, *, segment_id: str) -> list[ExtractedCitation]:
    """Extract citations from a single segment's plaintext.

    Each citation's `CharRange` is relative to the supplied `text`
    (which is the same as the segment's plaintext as returned by
    `CheckContext.get_text(segment)`).
    """
    if not text:
        return []

    out: list[ExtractedCitation] = []
    for raw in get_citations(text):
        span_start, span_end = raw.span()
        raw_text = text[span_start:span_end]

        parsed = _parsed_from_eyecite(raw)

        # eyecite's span covers only the reporter portion ("2010 WI 137"),
        # not the case name. For signal lookup we anchor at the start of
        # the case name when we know it, so "See Tews v. NHI, 2010 WI 137"
        # finds "See" instead of looking back from the bare reporter.
        anchor = span_start
        plaintiff = _plaintiff(raw)
        if plaintiff:
            idx = text.rfind(plaintiff, 0, span_start)
            if idx >= 0:
                anchor = idx
        signal = find_signal_before(text, anchor)
        if signal is not None:
            parsed.signal = signal[0]

        citation = Citation(
            id=str(uuid.uuid4()),
            raw_text=raw_text,
            span=CharRange(segment_id=segment_id, start=span_start, end=span_end),
            parsed=parsed,
            confidence=_confidence_for(raw),
        )

        out.append(
            ExtractedCitation(
                citation=citation,
                is_full_case=isinstance(raw, FullCaseCitation),
                is_short_form=isinstance(raw, (IdCitation, SupraCitation, ShortCaseCitation)),
                eyecite_type=type(raw).__name__,
            )
        )
    return out


def is_parallel_continuation(prev: ExtractedCitation, curr: ExtractedCitation) -> bool:
    """Two consecutive full case cites sharing a case name are parallel cites.

    Bluebook Rule 10.3.1: parallel citations share the same case name
    and signal; the pinpoint belongs to the case as a whole, not each
    reporter. So we should not separately fault each parallel cite for
    "missing pinpoint".
    """
    if not prev.is_full_case or not curr.is_full_case:
        return False
    a = prev.citation.parsed.case_name
    b = curr.citation.parsed.case_name
    if not a or not b:
        return False
    return a == b


def _plaintiff(raw) -> str | None:
    md = getattr(raw, "metadata", None)
    if md is None:
        return None
    return getattr(md, "plaintiff", None)


def all_citations(extracted: Sequence[ExtractedCitation]) -> list[Citation]:
    return [e.citation for e in extracted]


def _parsed_from_eyecite(raw) -> ParsedCitation:
    md = getattr(raw, "metadata", None)
    if md is None:
        return ParsedCitation()

    case_name = None
    plaintiff = getattr(md, "plaintiff", None)
    defendant = getattr(md, "defendant", None)
    if plaintiff and defendant:
        case_name = f"{plaintiff} v. {defendant}"
    elif plaintiff:
        case_name = plaintiff

    year_raw = getattr(md, "year", None)
    try:
        year = int(year_raw) if year_raw else None
    except (TypeError, ValueError):
        year = None

    return ParsedCitation(
        case_name=case_name,
        court=getattr(md, "court", None),
        year=year,
        pinpoint=getattr(md, "pin_cite", None),
        parenthetical=getattr(md, "parenthetical", None),
    )


def _confidence_for(raw) -> float:
    if isinstance(raw, FullCaseCitation):
        return 0.95
    if isinstance(raw, ShortCaseCitation):
        return 0.85
    if isinstance(raw, (IdCitation, SupraCitation)):
        return 0.80
    if isinstance(raw, CaseCitation):
        return 0.80
    return 0.60
