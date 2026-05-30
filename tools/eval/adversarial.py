"""Adversarial dataset generator.

Take a clean case from a hand-labeled dataset, apply structured
perturbations, and emit synthetic cases whose `expected` is the same
canonical form as the source. This expands the corpus 10–20× from a
small human-labeled seed.

Perturbation classes:

- whitespace_drift: collapse/expand spaces, add tabs.
- punctuation_drift: drop a comma, swap period for comma.
- abbreviation_drift: spell out / abbreviate reporter (T.6 variants).
- italics_drift: wrap case name in `*…*`, `_…_`, `<i>…</i>`.
- missing_pinpoint: drop the pinpoint and the comma before it.
- truncated_case_name: drop everything after the first defendant.
- ocr_noise: inject 1-2 character-level substitutions in non-key
  positions (numbers + punctuation untouched).

Each generated case carries `source="adversarial"`,
`metadata.parent_case_id`, `tags += ("adversarial", perturbation_name)`.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Callable, Iterable

from tools.eval.types import EvalCase


_OCR_TYPOS: dict[str, str] = {
    "v.": "V.",
    "v ": "V ",
    "L": "I",
    "O": "0",
    "I": "l",
}


@dataclass
class Perturbation:
    name: str
    apply: Callable[[str, random.Random], str]


def _whitespace_drift(s: str, rng: random.Random) -> str:
    # Randomly collapse 0-2 spaces or stretch them; never lossy.
    if rng.random() < 0.5:
        return re.sub(r" ", "  ", s, count=rng.randint(1, 3))
    return re.sub(r"  +", " ", s)


def _drop_one_comma(s: str, rng: random.Random) -> str:
    commas = [i for i, ch in enumerate(s) if ch == ","]
    if not commas:
        return s
    idx = rng.choice(commas)
    return s[:idx] + s[idx + 1 :]


def _alt_reporter(s: str, rng: random.Random) -> str:
    swaps = (
        ("Wis. 2d", "Wisc. 2d"),
        ("N.W.2d", "N.W. 2d"),
        ("U.S.", "U. S."),
        ("F.3d", "F. 3d"),
        ("L. Ed.", "L.Ed."),
    )
    for canonical, alt in swaps:
        if canonical in s and rng.random() < 0.5:
            return s.replace(canonical, alt, 1)
    return s


def _wrap_case_name_italics(s: str, rng: random.Random) -> str:
    # Find an "X v. Y" substring and wrap it.
    m = re.search(r"([A-Z][\w'\.]*(?:\s[A-Z][\w'\.]*)*\s+v\.\s+[A-Z][\w'\.\s,]*)", s)
    if not m:
        return s
    wrap = rng.choice([("*", "*"), ("_", "_"), ("<i>", "</i>")])
    case_name = m.group(1).rstrip(", ")
    return s.replace(case_name, f"{wrap[0]}{case_name}{wrap[1]}", 1)


def _drop_pinpoint(s: str, rng: random.Random) -> str:
    # Cut the last ", ¶ N" or ", N" pinpoint-looking tail.
    return re.sub(r",\s*(?:¶\s*\d+|\d+)(?=[,.\s]|$)", "", s, count=1)


def _ocr_noise(s: str, rng: random.Random) -> str:
    candidates = [k for k in _OCR_TYPOS if k in s]
    if not candidates:
        return s
    k = rng.choice(candidates)
    return s.replace(k, _OCR_TYPOS[k], 1)


def _truncated_case_name(s: str, rng: random.Random) -> str:
    # Drop trailing ", LLC" / ", Inc." style suffix from the defendant.
    return re.sub(r",\s*(LLC|Inc\.?|Corp\.?|L\.L\.P\.|LLP|Ltd\.?)", "", s, count=1)


PERTURBATIONS: tuple[Perturbation, ...] = (
    Perturbation("whitespace_drift", _whitespace_drift),
    Perturbation("dropped_comma", _drop_one_comma),
    Perturbation("alt_reporter_abbrev", _alt_reporter),
    Perturbation("italics_drift", _wrap_case_name_italics),
    Perturbation("missing_pinpoint", _drop_pinpoint),
    Perturbation("ocr_noise", _ocr_noise),
    Perturbation("truncated_case_name", _truncated_case_name),
)


def generate_adversarial(
    seed_cases: Iterable[EvalCase],
    *,
    per_case: int = 3,
    field: str = "raw",
    expected_field: str = "canonical",
    seed: int = 1729,
) -> list[EvalCase]:
    """For each seed case, generate `per_case` perturbed mutants.

    The mutant's `input[field]` is the perturbed text; its `expected`
    stays identical to the seed's (the system is supposed to recover
    the canonical form regardless).
    """
    rng = random.Random(seed)
    out: list[EvalCase] = []
    for seed_case in seed_cases:
        source_text = seed_case.input.get(field)
        if not isinstance(source_text, str):
            continue
        chosen = rng.sample(
            PERTURBATIONS, min(per_case, len(PERTURBATIONS))
        )
        for pert in chosen:
            perturbed = pert.apply(source_text, rng)
            if perturbed == source_text:
                continue
            new_input = dict(seed_case.input)
            new_input[field] = perturbed
            out.append(
                EvalCase(
                    id=f"{seed_case.id}__{pert.name}",
                    input=new_input,
                    expected=dict(seed_case.expected),
                    tags=tuple(seed_case.tags) + ("adversarial", pert.name),
                    difficulty="hard",
                    source="adversarial",
                    metadata={
                        **seed_case.metadata,
                        "parent_case_id": seed_case.id,
                        "perturbation": pert.name,
                    },
                )
            )
    return out
