"""Tests for programmatic + Bluebook-fuzzy scorers."""

from __future__ import annotations

from tools.eval.scorers import (
    BluebookFuzzy,
    ExactMatch,
    FieldMatch,
    SchemaValid,
    _bluebook_normalize,
)


def _input() -> dict:
    return {"raw": "x"}


def test_schema_valid():
    assert SchemaValid().score(
        candidate={"canonical": "Tews v. NHI"},
        gold={"canonical": "anything"},
        case_input=_input(),
    ).value == 1.0
    assert SchemaValid().score(
        candidate=None, gold={}, case_input=_input(),
    ).value == 0.0


def test_exact_match_canonical_field():
    sc = ExactMatch(field="canonical")
    assert sc.score(
        candidate={"canonical": "Tews v. NHI, LLC, 2010 WI 137"},
        gold={"canonical": "Tews v. NHI, LLC, 2010 WI 137"},
        case_input=_input(),
    ).value == 1.0
    assert sc.score(
        candidate={"canonical": "Tews"},
        gold={"canonical": "Tews v. NHI"},
        case_input=_input(),
    ).value == 0.0


def test_field_match_per_field_rate():
    sc = FieldMatch(fields=("case_name", "year", "court"))
    out = sc.score(
        candidate={"case_name": "Tews v. NHI", "year": 2010, "court": "WI"},
        gold={"case_name": "Tews v. NHI", "year": 2010, "court": "WI"},
        case_input=_input(),
    )
    assert out.value == 1.0

    out = sc.score(
        candidate={"case_name": "Tews v. NHI", "year": 2011, "court": "WI"},
        gold={"case_name": "Tews v. NHI", "year": 2010, "court": "WI"},
        case_input=_input(),
    )
    assert abs(out.value - 2 / 3) < 1e-9


def test_field_match_skips_unspecified_gold_fields():
    sc = FieldMatch(fields=("case_name", "pinpoint"))
    out = sc.score(
        candidate={"case_name": "X v. Y"},
        gold={"case_name": "X v. Y"},  # no pinpoint → skipped
        case_input=_input(),
    )
    assert out.value == 1.0


def test_bluebook_fuzzy_handles_italics():
    sc = BluebookFuzzy()
    assert sc.score(
        candidate={"canonical": "*Tews v. NHI, LLC*, 2010 WI 137"},
        gold={"canonical": "Tews v. NHI, LLC, 2010 WI 137"},
        case_input=_input(),
    ).value == 1.0
    assert sc.score(
        candidate={"canonical": "<i>Brown v. Holiday</i>, 2008 WI 49"},
        gold={"canonical": "Brown v. Holiday, 2008 WI 49"},
        case_input=_input(),
    ).value == 1.0


def test_bluebook_fuzzy_handles_reporter_aliases():
    sc = BluebookFuzzy()
    assert sc.score(
        candidate={"canonical": "Doe v. Roe, 100 Wisc. 2d 200"},
        gold={"canonical": "Doe v. Roe, 100 Wis. 2d 200"},
        case_input=_input(),
    ).value == 1.0
    assert sc.score(
        candidate={"canonical": "Miller v. Alabama, 567 U. S. 460"},
        gold={"canonical": "Miller v. Alabama, 567 U.S. 460"},
        case_input=_input(),
    ).value == 1.0


def test_bluebook_fuzzy_handles_whitespace_drift():
    sc = BluebookFuzzy()
    assert sc.score(
        candidate={"canonical": "Tews  v.  NHI,  LLC,  2010  WI  137"},
        gold={"canonical": "Tews v. NHI, LLC, 2010 WI 137"},
        case_input=_input(),
    ).value == 1.0


def test_bluebook_fuzzy_still_rejects_substantive_differences():
    sc = BluebookFuzzy()
    assert sc.score(
        candidate={"canonical": "Tews v. NHI, LLC, 2010 WI 137"},
        gold={"canonical": "Tews v. NHI, LLC, 2011 WI 137"},  # wrong year
        case_input=_input(),
    ).value == 0.0


def test_bluebook_normalize_idempotent():
    s = "*Tews* v. NHI,  LLC, 2010 WI 137."
    once = _bluebook_normalize(s)
    twice = _bluebook_normalize(once)
    assert once == twice
