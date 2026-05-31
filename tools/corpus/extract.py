"""Turn brief PDFs (or raw text) into candidate EvalCases.

For each full case citation eyecite finds in the brief text, emit one
candidate case:

  - `input.raw`         = the citation as it appears in the brief
                          (the eyecite span, plus the case-name prefix
                          when we can find it).
  - `input.context`     = ~200 chars around the citation, sentence-trimmed.
  - `input.jurisdiction` = "WI" by default.
  - `expected.canonical` = our best-guess canonical form, derived from
                           eyecite's parsed metadata. The human triager
                           accepts / edits this during labeling.
  - `expected.case_name`, `year`, `pinpoint`, `court`, `reporter` —
                           whatever eyecite gave us.
  - `tags`              = ["wi", "wicourts_scraped", "<perturbation
                           tag if applicable>"].
  - `source`            = "wicourts_scraped".
  - `metadata`          = {brief_url, page_number, raw_span}.

The candidate's `expected` is a starting point, not ground truth. The
triage step is where a human turns it into a real label.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from legal_citations import ExtractedCitation, extract_citations_in_text
from legal_citations.parser import is_parallel_continuation
from tools.corpus.pdf import (
    ExtractedPDF,
    page_number_for_offset,
    surrounding_text,
)
from tools.eval.types import EvalCase


@dataclass(frozen=True)
class ExtractedCandidate:
    """One pre-triage candidate, with provenance + context."""

    case: EvalCase
    brief_source: str
    page_number: int


def extract_candidates_from_pdf(
    pdf: ExtractedPDF,
    *,
    brief_source: str,
    jurisdiction: str = "WI",
    context_window: int = 200,
    id_prefix: str | None = None,
) -> list[ExtractedCandidate]:
    """Walk a parsed PDF, emit one candidate per full case citation.

    `brief_source` is recorded in metadata (a URL or filename works).
    """
    citations = extract_citations_in_text(pdf.text, segment_id="brief")
    candidates: list[ExtractedCandidate] = []
    seen_case_names: set[str] = set()
    prev: ExtractedCitation | None = None

    for ec in citations:
        if not ec.is_full_case:
            prev = ec
            continue
        if not ec.citation.parsed.case_name:
            # eyecite couldn't find a case name; almost certainly
            # boilerplate or OCR noise. Skip rather than waste
            # triage attention.
            prev = ec
            continue
        # Parallel-cite continuation: same case, alternate reporter.
        # Skip — the lead cite already became a candidate.
        if prev is not None and is_parallel_continuation(prev, ec):
            prev = ec
            continue
        # Dedupe: a single case may be cited many times in one brief.
        # First occurrence wins; case-name match is the strongest
        # signal that's robust to pinpoint drift.
        if ec.citation.parsed.case_name in seen_case_names:
            prev = ec
            continue
        seen_case_names.add(ec.citation.parsed.case_name)
        prev = ec
        raw_with_name = _full_raw(pdf.text, ec)

        page_no = page_number_for_offset(pdf.pages, ec.citation.span.start)
        context = surrounding_text(
            pdf.text,
            ec.citation.span.start,
            ec.citation.span.end,
            window=context_window,
        )
        canonical_guess = _canonical_guess_from_eyecite(ec)
        case_id = _make_case_id(brief_source, len(candidates), id_prefix)

        eval_case = EvalCase(
            id=case_id,
            input={
                "raw": raw_with_name,
                "context": context,
                "jurisdiction": jurisdiction,
            },
            expected={
                k: v
                for k, v in {
                    "canonical": canonical_guess,
                    "case_name": ec.citation.parsed.case_name,
                    "year": ec.citation.parsed.year,
                    "pinpoint": ec.citation.parsed.pinpoint,
                    "court": ec.citation.parsed.court,
                    "reporter": ec.citation.parsed.reporter,
                }.items()
                if v is not None
            },
            tags=("wi", "wicourts_scraped"),
            difficulty="medium",
            source="wicourts_scraped",
            metadata={
                "brief_source": brief_source,
                "page_number": page_no,
                "raw_span": [
                    ec.citation.span.start,
                    ec.citation.span.end,
                ],
            },
        )
        candidates.append(
            ExtractedCandidate(
                case=eval_case,
                brief_source=brief_source,
                page_number=page_no,
            )
        )
    return candidates


def extract_candidates_from_text(
    text: str,
    *,
    brief_source: str,
    jurisdiction: str = "WI",
    context_window: int = 200,
    id_prefix: str | None = None,
) -> list[ExtractedCandidate]:
    """Same as extract_candidates_from_pdf but for already-extracted text."""
    pseudo = ExtractedPDF(
        text=text,
        pages=(),
    )
    # Without page info, page_number_for_offset returns 1; that's fine.
    return extract_candidates_from_pdf(
        pseudo,
        brief_source=brief_source,
        jurisdiction=jurisdiction,
        context_window=context_window,
        id_prefix=id_prefix,
    )


def write_candidates(
    candidates: Iterable[ExtractedCandidate], path
) -> None:
    """Persist candidates to a JSONL file the triage tool can read."""
    from tools.eval.dataset import write_dataset
    write_dataset(path, (c.case for c in candidates))


def _canonical_guess_from_eyecite(ec: ExtractedCitation) -> str:
    """Best-effort canonical form from eyecite's metadata.

    The triager accepts/edits this; we don't try to perfect it here.
    Pattern: "<case_name>, <reporter cite>, <pinpoint?>" with the
    year in parens when known.
    """
    parts: list[str] = []
    if ec.citation.parsed.case_name:
        parts.append(ec.citation.parsed.case_name)
    cite_token = ec.citation.raw_text
    parts.append(cite_token)
    pin = ec.citation.parsed.pinpoint
    if pin and pin not in cite_token:
        parts.append(pin)
    base = ", ".join(parts)
    if ec.citation.parsed.year and str(ec.citation.parsed.year) not in base:
        base = f"{base} ({ec.citation.parsed.year})"
    return base


def _full_raw(text: str, ec: ExtractedCitation) -> str:
    """Reconstruct the citation including the case-name prefix.

    Eyecite's span only covers the reporter portion ("2010 WI 137"),
    not the preceding case name. For triage we want the human to see
    the whole citation, so we look back from the span start, find the
    case-name plaintiff, and include text from there forward.
    """
    plaintiff = ec.citation.parsed.case_name and ec.citation.parsed.case_name.split(
        " v. "
    )[0]
    start = ec.citation.span.start
    if plaintiff:
        idx = text.rfind(plaintiff, max(0, start - 200), start)
        if idx >= 0:
            start = idx
    end = ec.citation.span.end
    return _normalize_whitespace(text[start:end])


def _normalize_whitespace(s: str) -> str:
    s = s.replace("-\n", "")
    return " ".join(s.split())


def _make_case_id(brief_source: str, ordinal: int, prefix: str | None) -> str:
    if prefix:
        return f"{prefix}__{ordinal:04d}"
    # Derive from brief filename if available.
    import re
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(brief_source).split("/")[-1])
    stem = stem.replace(".pdf", "")[:40].strip("_")
    return f"{stem or 'brief'}__{ordinal:04d}"
