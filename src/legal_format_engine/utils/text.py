"""Text processing utilities for legal documents."""

from __future__ import annotations

import re
import unicodedata

# Words that should stay lowercase in title case (unless first/last)
TITLE_CASE_EXCEPTIONS = {
    "a", "an", "the", "and", "but", "or", "nor", "for", "yet", "so",
    "at", "by", "in", "of", "on", "to", "up", "as", "is", "if",
    "v.", "vs.", "v",
}

# Common legal abbreviations that should keep specific casing
LEGAL_ABBREVIATIONS = {
    "id.": "Id.",
    "cf.": "Cf.",
    "e.g.": "e.g.",
    "i.e.": "i.e.",
}


def to_upper(s: str) -> str:
    """Convert text to uppercase."""
    return s.upper()


def to_title_case(s: str) -> str:
    """Convert text to title case with legal-aware exceptions.

    >>> to_title_case("statement of the case")
    'Statement of the Case'
    >>> to_title_case("STATEMENT OF THE CASE")
    'Statement of the Case'
    """
    words = s.strip().split()
    if not words:
        return s
    result = []
    for i, word in enumerate(words):
        lower = word.lower()
        if i == 0 or i == len(words) - 1:
            # First and last words always capitalized
            result.append(word.capitalize())
        elif lower in TITLE_CASE_EXCEPTIONS:
            result.append(lower)
        else:
            result.append(word.capitalize())
    return " ".join(result)


def to_sentence_case(s: str) -> str:
    """Convert text to sentence case (first letter capitalized, rest lowercase).

    >>> to_sentence_case("STATEMENT OF FACTS")
    'Statement of facts'
    """
    s = s.strip()
    if not s:
        return s
    return s[0].upper() + s[1:].lower()


def normalize_whitespace(s: str) -> str:
    """Collapse multiple whitespace characters into single spaces and strip.

    >>> normalize_whitespace("  hello   world  ")
    'hello world'
    """
    return re.sub(r"\s+", " ", s).strip()


def normalize_for_matching(s: str) -> str:
    """Normalize a string for fuzzy heading comparison.

    Strips numbering prefixes, lowercases, removes punctuation, collapses whitespace.

    >>> normalize_for_matching("I. STATEMENT OF THE CASE")
    'statement of the case'
    >>> normalize_for_matching("Statement of Facts")
    'statement of facts'
    """
    from legal_format_engine.utils.numbering import strip_numbering_prefix

    _, text = strip_numbering_prefix(s)
    text = text.lower()
    # Remove punctuation except periods in abbreviations
    text = re.sub(r"[^\w\s.]", "", text)
    # Remove trailing periods
    text = text.rstrip(".")
    text = normalize_whitespace(text)
    return text


def fuzzy_heading_match(heading: str, candidates: dict[str, list[str]]) -> str | None:
    """Match a heading against canonical names and their aliases.

    Args:
        heading: The heading text to match.
        candidates: Dict mapping section_id -> list of acceptable names/aliases.

    Returns:
        The matched section_id, or None.

    >>> aliases = {"statement_of_facts": ["Statement of Facts", "Facts", "Factual Background"]}
    >>> fuzzy_heading_match("STATEMENT OF FACTS", aliases)
    'statement_of_facts'
    >>> fuzzy_heading_match("Facts", aliases)
    'statement_of_facts'
    """
    if not heading or not heading.strip():
        return None

    normalized = normalize_for_matching(heading)
    if not normalized:
        return None

    # First pass: exact match after normalization
    for section_id, names in candidates.items():
        for name in names:
            if normalize_for_matching(name) == normalized:
                return section_id

    # Second pass: substring containment
    for section_id, names in candidates.items():
        for name in names:
            norm_name = normalize_for_matching(name)
            if norm_name in normalized or normalized in norm_name:
                return section_id

    return None


def is_likely_heading(line: str) -> bool:
    """Heuristic check if a line looks like a section heading.

    A heading is typically short, may be all caps, may start with numbering.
    """
    line = line.strip()
    if not line:
        return False
    # Too long to be a heading
    if len(line) > 150:
        return False
    # All caps and short -> likely heading
    if line.isupper() and len(line) < 80:
        return True
    # Starts with numbering prefix -> likely heading
    from legal_format_engine.utils.numbering import NUMBERING_PREFIX_PATTERN

    if NUMBERING_PREFIX_PATTERN.match(line) and len(line) < 120:
        return True
    return False


def strip_unicode_control(s: str) -> str:
    """Remove Unicode control characters except standard whitespace."""
    return "".join(
        c for c in s
        if not unicodedata.category(c).startswith("C") or c in "\n\r\t "
    )
