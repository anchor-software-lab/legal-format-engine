"""Tests for the extract → candidate EvalCase pipeline."""

from __future__ import annotations

from pathlib import Path

from tools.corpus.extract import (
    extract_candidates_from_text,
    write_candidates,
    _canonical_guess_from_eyecite,
)
from tools.eval.dataset import load_dataset


_BRIEF_TEXT = (
    "We review summary judgment de novo. See Tews v. NHI, LLC, 2010 WI "
    "137, ¶ 4, 330 Wis. 2d 389. The trial court erred. "
    "See also Brown v. Holiday, 2008 WI 49, ¶ 12. "
    "Id. at ¶ 14. Compare Smith v. Jones, 921 F.3d 1234 (7th Cir. 2019)."
)


def test_extracts_full_case_citations_only():
    out = extract_candidates_from_text(_BRIEF_TEXT, brief_source="brief.pdf")
    case_names = {c.case.expected.get("case_name") for c in out}
    # Full case cites: Tews, Brown, Smith. Id. is a short form — skipped.
    assert "Tews v. NHI, LLC" in case_names
    assert "Brown v. Holiday" in case_names
    # eyecite occasionally folds the signal into plaintiff; tolerate
    # either form here.
    assert any(name and "Smith" in name and "Jones" in name for name in case_names)


def test_candidate_input_has_raw_context_jurisdiction():
    out = extract_candidates_from_text(
        _BRIEF_TEXT, brief_source="brief.pdf", jurisdiction="WI"
    )
    assert out, "expected at least one candidate"
    for c in out:
        assert "raw" in c.case.input
        assert c.case.input["raw"]
        assert "context" in c.case.input
        assert c.case.input["context"]
        assert c.case.input["jurisdiction"] == "WI"
        cn = c.case.expected.get("case_name", "")
        assert cn and any(
            tok in c.case.input["context"] for tok in cn.split()
        )


def test_candidate_expected_has_canonical_guess():
    out = extract_candidates_from_text(_BRIEF_TEXT, brief_source="brief.pdf")
    tews = next(c for c in out if c.case.expected.get("case_name") == "Tews v. NHI, LLC")
    canonical = tews.case.expected["canonical"]
    assert "Tews v. NHI, LLC" in canonical
    assert "2010 WI 137" in canonical


def test_candidate_metadata_records_provenance():
    out = extract_candidates_from_text(_BRIEF_TEXT, brief_source="/abs/path/brief.pdf")
    for c in out:
        assert c.case.metadata["brief_source"] == "/abs/path/brief.pdf"
        assert isinstance(c.case.metadata["page_number"], int)
        assert len(c.case.metadata["raw_span"]) == 2


def test_candidate_source_tag_marks_origin():
    out = extract_candidates_from_text(_BRIEF_TEXT, brief_source="brief.pdf")
    for c in out:
        assert c.case.source == "wicourts_scraped"
        assert "wicourts_scraped" in c.case.tags


def test_dedupe_same_citation_in_brief():
    repeated = _BRIEF_TEXT + " As Tews v. NHI, LLC, 2010 WI 137 again held..."
    out = extract_candidates_from_text(repeated, brief_source="brief.pdf")
    tews_hits = [
        c for c in out if c.case.expected.get("case_name") == "Tews v. NHI, LLC"
    ]
    # First occurrence wins; repeated citation suppressed.
    assert len(tews_hits) == 1


def test_skips_citations_without_case_name():
    text = "Cite without name: 2010 WI 137 is on point."  # eyecite has no plaintiff
    out = extract_candidates_from_text(text, brief_source="x")
    # If eyecite extracted no case_name, we drop the candidate.
    assert all(c.case.expected.get("case_name") for c in out)


def test_write_candidates_produces_loadable_jsonl(tmp_path: Path):
    out = extract_candidates_from_text(_BRIEF_TEXT, brief_source="brief.pdf")
    jsonl = tmp_path / "candidates.jsonl"
    write_candidates(out, jsonl)
    loaded = load_dataset(jsonl)
    assert len(loaded) == len(out)
    # Round-trip preserves the id.
    assert {c.id for c in loaded} == {c.case.id for c in out}


def test_canonical_guess_includes_pinpoint_when_present():
    out = extract_candidates_from_text(_BRIEF_TEXT, brief_source="x")
    tews = next(c for c in out if c.case.expected.get("case_name") == "Tews v. NHI, LLC")
    assert "¶ 4" in tews.case.expected["canonical"]


def test_id_prefix_overrides_default_naming():
    out = extract_candidates_from_text(
        _BRIEF_TEXT, brief_source="x", id_prefix="wi_2024AP1"
    )
    for c in out:
        assert c.case.id.startswith("wi_2024AP1__")
