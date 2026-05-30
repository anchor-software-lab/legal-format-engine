"""Bluebook introductory signals (Rule 1.2 / Table T.1.4).

The signals are grouped into four families that have a required order
when multiple appear in a citation string (Rule 1.3):

  1. SUPPORTING:     [no signal] | e.g. | accord | see | see also | cf.
  2. COMPARISON:     compare ... with ...
  3. CONTRADICTING:  contra | but see | but cf.
  4. BACKGROUND:     see generally

This module is text-only — no italicization checks (those require
per-run style info that the v0 parser doesn't yet expose).
"""

from __future__ import annotations

import re
from enum import Enum


class SignalKind(str, Enum):
    SUPPORTING = "supporting"
    COMPARISON = "comparison"
    CONTRADICTING = "contradicting"
    BACKGROUND = "background"


# Canonical signal phrases, mapped to their family.
# Lowercase, no trailing punctuation. Order matters: longer phrases
# must be matched before shorter ones (e.g. "see also" before "see").
SIGNALS: tuple[tuple[str, SignalKind], ...] = (
    ("see generally", SignalKind.BACKGROUND),
    ("but see", SignalKind.CONTRADICTING),
    ("but cf.", SignalKind.CONTRADICTING),
    ("see also", SignalKind.SUPPORTING),
    ("see, e.g.,", SignalKind.SUPPORTING),
    ("e.g.,", SignalKind.SUPPORTING),
    ("accord", SignalKind.SUPPORTING),
    ("contra", SignalKind.CONTRADICTING),
    ("compare", SignalKind.COMPARISON),
    ("see", SignalKind.SUPPORTING),
    ("cf.", SignalKind.SUPPORTING),
)

# Maximum characters to look backward from a citation start when hunting
# for the signal. 60 chars covers everything in T.1.4 with room to
# spare; constraining the window keeps us from accidentally matching a
# stray "see" three sentences earlier.
_LOOKBACK_CHARS = 60

# Sentence-end markers that stop the backward scan. Anything before one
# of these can't be the signal for this citation.
_STOP_CHARS = ".;"


# Words that, in any combination, look like an introductory signal.
# Used to distinguish "malformed signal" prose from genuinely
# unsignaled citations.
_SIGNAL_WORDS = {
    "see",
    "also",
    "but",
    "cf",
    "cf.",
    "e",
    "e.g.",
    "e.g.,",
    "accord",
    "compare",
    "contra",
    "generally",
}


def find_signal_before(
    text: str, citation_start: int
) -> tuple[str, SignalKind | None, int] | None:
    """Find the Bluebook signal immediately preceding a citation.

    Returns `(signal_text, kind, start_offset)` where:
      - `kind` is a `SignalKind` if the signal exactly matches one in
        T.1.4.
      - `kind` is `None` if the preceding prose is "signal-shaped"
        (composed only of signal words) but not a canonical signal —
        i.e. a malformed signal like "See, also,".
      - Returns `None` if no signal is present at all.

    Algorithm: walk backward up to `_LOOKBACK_CHARS`, stop at the first
    sentence-end punctuation, then test each canonical signal (longest
    first) against the trailing portion of that window. If no canonical
    match, fall back to the signal-shape heuristic.
    """
    if citation_start <= 0:
        return None

    window_start = max(0, citation_start - _LOOKBACK_CHARS)
    window = text[window_start:citation_start]

    last_stop = max((window.rfind(c) for c in _STOP_CHARS), default=-1)
    candidate = window[last_stop + 1 :]

    # Trim the join between signal and citation: trailing whitespace
    # and at most one separating comma. Track how many characters we
    # stripped so we can map back to absolute indices below.
    trimmed = candidate.rstrip()
    if trimmed.endswith(","):
        trimmed = trimmed[:-1].rstrip()
    if not trimmed:
        return None

    lower = trimmed.lower()

    # 1) Try canonical (longest-first) match abutting the citation.
    for signal, kind in SIGNALS:
        if lower.endswith(signal):
            signal_offset_in_trimmed = len(trimmed) - len(signal)
            if signal_offset_in_trimmed > 0:
                preceding = trimmed[signal_offset_in_trimmed - 1]
                if not preceding.isspace():
                    continue
            signal_start = (
                window_start + (last_stop + 1) + signal_offset_in_trimmed
            )
            return trimmed[signal_offset_in_trimmed:], kind, signal_start

    # 2) Malformed-signal fallback: keep only the trailing run of
    # "signal-shaped" tokens. If everything we have is signal-shaped,
    # treat it as a malformed signal.
    tokens = trimmed.split()
    if not tokens:
        return None

    # Walk from the right, collecting signal-shaped tokens until we
    # hit a non-signal token (which means it's prose, not a signal).
    kept: list[str] = []
    for token in reversed(tokens):
        if token.lower().strip(",.") in {w.strip(",.") for w in _SIGNAL_WORDS}:
            kept.append(token)
        else:
            break
    if not kept:
        return None
    kept.reverse()
    malformed = " ".join(kept)
    # Locate the malformed signal in the trimmed candidate.
    malformed_offset = len(trimmed) - len(malformed)
    if malformed_offset > 0:
        preceding = trimmed[malformed_offset - 1]
        if not preceding.isspace():
            return None
    signal_start = window_start + (last_stop + 1) + malformed_offset
    return malformed, None, signal_start


def classify_signal_text(signal: str) -> SignalKind | None:
    """Return the SignalKind of a signal phrase, or None if not canonical.

    Match is exact (modulo whitespace and case): trailing commas /
    periods are part of the canonical form for some signals (e.g.,
    "e.g.," and "cf.") so we don't strip them. Inputs like "cf,"
    (comma instead of period) or "see also," (trailing comma) are
    rejected as non-canonical.
    """
    if not signal:
        return None
    normalized = signal.strip().lower()
    for canonical, kind in SIGNALS:
        if normalized == canonical:
            return kind
    return None


# Required order within a citation string (Rule 1.3).
_ORDER = (
    SignalKind.SUPPORTING,
    SignalKind.COMPARISON,
    SignalKind.CONTRADICTING,
    SignalKind.BACKGROUND,
)


def order_index(kind: SignalKind) -> int:
    return _ORDER.index(kind)


_NORMALIZED_PUNCTUATION = re.compile(r"\s+")


def normalize_signal_whitespace(signal: str) -> str:
    return _NORMALIZED_PUNCTUATION.sub(" ", signal.strip())
