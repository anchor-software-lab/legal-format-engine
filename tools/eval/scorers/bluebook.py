"""Bluebook-aware fuzzy scorer.

Two Bluebook strings can be equivalent even when they're not
byte-identical:

- Whitespace differences (`"410 U.S. 113"` vs `"410 U. S. 113"`).
- Reporter abbreviation variants per Table T.6 / T.10
  (`"Wis. 2d"` vs `"Wisc. 2d"`, `"N.W.2d"` vs `"N. W. 2d"`).
- Italic markup wrappers (`*Tews*`, `_Tews_`, `<i>Tews</i>`).
- Punctuation spacing (`"Co., Inc."` vs `"Co. , Inc."`).

`BluebookFuzzy.score()` normalizes both strings before compare and
returns 1.0 / 0.0. We pair it with `ExactMatch` for the byte-identical
gate; `BluebookFuzzy` answers "are these the same citation under
Bluebook?"

The normalization tables are small by design — we add an entry the
first time a test case fails for a recognizably equivalent form.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from tools.eval.scorers.base import ScoreResult


# Reporter-abbreviation normalization. Keys are "canonical" Bluebook
# forms; values are alternates we map TO the canonical. Order
# matters; longest-first so subreporters match before reporters.
_REPORTER_ALIASES: dict[str, tuple[str, ...]] = {
    "U.S.": ("US", "U. S.", "U.s.", "u.s."),
    "S. Ct.": ("S.Ct.", "S Ct", "Sct."),
    "L. Ed. 2d": ("L.Ed.2d", "L Ed 2d", "L.Ed. 2d"),
    "L. Ed.": ("L.Ed.", "L Ed"),
    "F.3d": ("F. 3d", "F 3d"),
    "F.2d": ("F. 2d", "F 2d"),
    "F. Supp. 3d": ("F.Supp.3d", "F Supp 3d"),
    "F. Supp. 2d": ("F.Supp.2d", "F Supp 2d"),
    "F. Supp.": ("F.Supp.", "F Supp"),
    "N.W.2d": ("N.W. 2d", "N. W. 2d", "N W 2d", "NW2d"),
    "N.E.2d": ("N.E. 2d", "N. E. 2d", "N E 2d", "NE2d"),
    "S.W.3d": ("S.W. 3d", "S. W. 3d", "S W 3d"),
    "P.3d": ("P. 3d", "P 3d"),
    "Wis. 2d": ("Wisc. 2d", "Wis.2d", "Wis 2d"),
    "Cal. 4th": ("Cal.4th", "Cal 4th"),
}


# Compiled finder for italic markup: `*x*`, `_x_`, `<i>x</i>`.
_ITALIC_MARKUP = re.compile(
    r"<i>|</i>|<em>|</em>|"   # html
    r"(?<![*\w])\*(?!\s)|(?<!\s)\*(?![*\w])|"  # markdown asterisks
    r"(?<![_\w])_(?!\s)|(?<!\s)_(?![_\w])"     # markdown underscores
)

_MULTISPACE = re.compile(r"\s+")


def _bluebook_normalize(s: str) -> str:
    """Strip italic markup, collapse whitespace, fold reporter variants."""
    s = _ITALIC_MARKUP.sub("", s)
    s = _MULTISPACE.sub(" ", s).strip()
    # Reporter folding: replace each alias with its canonical key.
    # Order matters; sort canonical keys longest-first to avoid
    # "U.S." matching inside "U.S. Supreme Court" prematurely.
    for canonical in sorted(_REPORTER_ALIASES, key=len, reverse=True):
        for alias in _REPORTER_ALIASES[canonical]:
            s = s.replace(alias, canonical)
    # Normalize comma + space → ", " (no double space after comma).
    s = re.sub(r"\s*,\s*", ", ", s)
    # Drop trailing punctuation that doesn't change meaning.
    s = s.rstrip(".;,")
    return s


@dataclass
class BluebookFuzzy:
    """1.0 iff Bluebook-normalized candidate equals Bluebook-normalized gold."""

    field: str = "canonical"
    name: str = "bluebook_fuzzy"

    def score(
        self,
        *,
        candidate: dict[str, Any] | None,
        gold: dict[str, Any],
        case_input: dict[str, Any],
    ) -> ScoreResult:
        if candidate is None:
            return ScoreResult(self.name, 0.0, {"reason": "no candidate"})
        c = _bluebook_normalize(str(candidate.get(self.field, "")))
        g = _bluebook_normalize(str(gold.get(self.field, "")))
        return ScoreResult(
            self.name,
            1.0 if c == g else 0.0,
            {"normalized_candidate": c, "normalized_gold": g},
        )
