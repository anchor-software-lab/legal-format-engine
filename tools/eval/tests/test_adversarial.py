"""Tests for the adversarial mutant generator."""

from __future__ import annotations

from tools.eval.adversarial import PERTURBATIONS, generate_adversarial
from tools.eval.types import EvalCase


def _seed_case() -> EvalCase:
    return EvalCase(
        id="seed_1",
        input={
            "raw": "Tews v. NHI, LLC, 2010 WI 137, ¶ 4, 330 Wis. 2d 389",
            "context": "we review de novo",
            "jurisdiction": "WI",
        },
        expected={
            "canonical": "Tews v. NHI, LLC, 2010 WI 137, ¶ 4, 330 Wis. 2d 389",
            "case_name": "Tews v. NHI, LLC",
            "year": 2010,
        },
        tags=("wi", "neutral"),
        difficulty="easy",
        source="human",
    )


def test_mutants_inherit_expected_and_metadata():
    seed = _seed_case()
    mutants = generate_adversarial([seed], per_case=3, seed=42)
    assert len(mutants) >= 1
    for m in mutants:
        assert m.expected == seed.expected
        assert m.source == "adversarial"
        assert "adversarial" in m.tags
        assert m.metadata["parent_case_id"] == "seed_1"
        assert m.metadata["perturbation"] in {p.name for p in PERTURBATIONS}
        assert m.difficulty == "hard"


def test_mutants_have_distinct_ids():
    seed = _seed_case()
    mutants = generate_adversarial([seed], per_case=5, seed=7)
    assert len({m.id for m in mutants}) == len(mutants)
    for m in mutants:
        assert m.id.startswith("seed_1__")


def test_mutated_raw_differs_from_seed():
    seed = _seed_case()
    mutants = generate_adversarial([seed], per_case=7, seed=3)
    differences = sum(1 for m in mutants if m.input["raw"] != seed.input["raw"])
    assert differences >= 1  # at least one perturbation actually changed text


def test_seeded_generator_is_deterministic():
    seed = _seed_case()
    a = generate_adversarial([seed], per_case=3, seed=99)
    b = generate_adversarial([seed], per_case=3, seed=99)
    assert [m.id for m in a] == [m.id for m in b]
    assert [m.input["raw"] for m in a] == [m.input["raw"] for m in b]


def test_skips_cases_without_text_field():
    bad = EvalCase(
        id="x",
        input={"not_raw": 42},
        expected={"canonical": "y"},
    )
    mutants = generate_adversarial([bad], per_case=3, seed=1)
    assert mutants == []
