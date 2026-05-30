"""Tests for the eyecite-backed citation parser."""

from __future__ import annotations

from legal_citations import all_citations, extract_citations_in_text


SAMPLE = (
    "We review summary judgment de novo. See Tews v. NHI, LLC, 2010 WI 137, "
    "¶ 4, 330 Wis. 2d 389, 793 N.W.2d 860. See also Brown v. Holiday, "
    "2008 WI 49. Id. at ¶ 14. But see Smith v. Jones, 100 U.S. 1 (1990)."
)


def test_extracts_multiple_citations():
    extracted = extract_citations_in_text(SAMPLE, segment_id="seg-1")
    assert len(extracted) >= 4

    types = {e.eyecite_type for e in extracted}
    assert "FullCaseCitation" in types
    assert "IdCitation" in types


def test_citation_spans_anchor_to_segment():
    extracted = extract_citations_in_text(SAMPLE, segment_id="seg-1")
    for e in extracted:
        assert e.citation.span.segment_id == "seg-1"
        # The raw_text should be exactly what the span covers in SAMPLE.
        assert SAMPLE[e.citation.span.start : e.citation.span.end] == e.citation.raw_text


def test_signal_is_recorded_on_citation():
    extracted = extract_citations_in_text(SAMPLE, segment_id="seg-1")
    tews = next(e for e in extracted if "Tews" in (e.citation.parsed.case_name or ""))
    assert tews.citation.parsed.signal is not None
    assert tews.citation.parsed.signal.lower() == "see"


def test_pinpoint_extracted_when_present():
    extracted = extract_citations_in_text(SAMPLE, segment_id="seg-1")
    tews = next(e for e in extracted if "Tews" in (e.citation.parsed.case_name or ""))
    assert tews.citation.parsed.pinpoint is not None
    assert "4" in tews.citation.parsed.pinpoint


def test_pinpoint_missing_on_brown():
    extracted = extract_citations_in_text(SAMPLE, segment_id="seg-1")
    brown = next(
        e for e in extracted if "Brown" in (e.citation.parsed.case_name or "")
    )
    assert brown.citation.parsed.pinpoint is None
    assert brown.is_full_case is True


def test_empty_text_returns_empty_list():
    assert extract_citations_in_text("", segment_id="seg-1") == []


def test_text_without_citations_returns_empty_list():
    assert extract_citations_in_text("Just prose, no citations.", segment_id="seg-1") == []


def test_all_citations_unwraps():
    extracted = extract_citations_in_text(SAMPLE, segment_id="seg-1")
    cites = all_citations(extracted)
    assert len(cites) == len(extracted)
    assert all(c.id for c in cites)


def test_full_case_flag_set():
    extracted = extract_citations_in_text(SAMPLE, segment_id="seg-1")
    full_count = sum(1 for e in extracted if e.is_full_case)
    short_count = sum(1 for e in extracted if e.is_short_form)
    assert full_count >= 3  # Tews lead, Brown, Smith
    assert short_count >= 1  # Id.
