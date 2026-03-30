"""Text utility functions."""

from __future__ import annotations
import re
import unicodedata


def normalize_whitespace(text: str) -> str:
    """Collapse multiple whitespace to single spaces and strip."""
    return re.sub(r"\s+", " ", text).strip()


def normalize_heading(text: str) -> str:
    """Normalize heading text for comparison: lowercase, strip punctuation, collapse whitespace."""
    text = text.lower().strip()
    text = re.sub(r"^[ivxlcdm]+\.\s*", "", text)  # Roman numeral prefix
    text = re.sub(r"^[a-z]\.\s*", "", text)  # Letter prefix
    text = re.sub(r"^\d+\.\s*", "", text)  # Number prefix
    text = re.sub(r"[^\w\s]", "", text)
    return normalize_whitespace(text)


def is_all_caps(text: str) -> bool:
    """Check if text is all uppercase (ignoring non-alpha chars)."""
    alpha = "".join(c for c in text if c.isalpha())
    return bool(alpha) and alpha == alpha.upper()


def to_all_caps(text: str) -> str:
    return text.upper()


def to_title_case(text: str) -> str:
    minor_words = {"a", "an", "the", "and", "but", "or", "for", "nor", "of", "in", "on", "at", "to", "by", "with"}
    words = text.split()
    result = []
    for i, word in enumerate(words):
        if i == 0 or word.lower() not in minor_words:
            result.append(word.capitalize())
        else:
            result.append(word.lower())
    return " ".join(result)


def to_sentence_case(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:].lower()


def fuzzy_heading_match(heading: str, candidates: dict[str, list[str]]) -> str | None:
    """Match a heading to a section type using fuzzy matching against aliases.

    Returns the section_type key if matched, None otherwise.
    """
    if not heading or not heading.strip():
        return None

    normalized = normalize_heading(heading)
    if not normalized:
        return None

    # Exact match on normalized form
    for section_type, aliases in candidates.items():
        for alias in aliases:
            if normalize_heading(alias) == normalized:
                return section_type

    # Substring match
    for section_type, aliases in candidates.items():
        for alias in aliases:
            norm_alias = normalize_heading(alias)
            if normalized in norm_alias or norm_alias in normalized:
                return section_type

    return None


def strip_non_ascii(text: str) -> str:
    """Remove non-ASCII characters."""
    return "".join(c for c in text if ord(c) < 128)


def remove_diacritics(text: str) -> str:
    """Remove diacritical marks."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))
