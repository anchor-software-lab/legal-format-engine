"""Numbering utility functions for legal document headings."""

from __future__ import annotations
import re

ROMAN_MAP = [
    (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
    (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
    (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
]


def to_roman(n: int) -> str:
    """Convert integer to Roman numeral string."""
    if n <= 0:
        return ""
    result = []
    for value, numeral in ROMAN_MAP:
        while n >= value:
            result.append(numeral)
            n -= value
    return "".join(result)


def from_roman(s: str) -> int:
    """Convert Roman numeral string to integer."""
    s = s.upper().strip()
    roman_values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    prev = 0
    for c in reversed(s):
        val = roman_values.get(c, 0)
        if val < prev:
            total -= val
        else:
            total += val
        prev = val
    return total


def to_alpha(n: int, upper: bool = True) -> str:
    """Convert 1-based index to letter (A=1, B=2, ...)."""
    if n <= 0 or n > 26:
        return ""
    c = chr(ord("A") + n - 1)
    return c if upper else c.lower()


def generate_prefix(index: int, numbering_type: str | None = None) -> str:
    """Generate a numbering prefix.

    Args:
        index: 1-based index
        numbering_type: 'roman', 'alpha', 'arabic', or None
    """
    if numbering_type is None:
        return ""
    if numbering_type == "roman":
        return f"{to_roman(index)}."
    elif numbering_type == "alpha":
        return f"{to_alpha(index)}."
    elif numbering_type == "arabic":
        return f"{index}."
    return ""


_PREFIX_PATTERN = re.compile(
    r"^(?:"
    r"(?P<roman>[IVXLCDM]+)\.\s*"
    r"|(?P<alpha>[A-Z])\.\s*"
    r"|(?P<arabic>\d+)\.\s*"
    r")",
    re.IGNORECASE,
)


def strip_numbering_prefix(text: str) -> str:
    """Remove a leading numbering prefix (Roman, alpha, arabic) from text.

    Returns the text without the prefix, or the original text if no prefix found.
    """
    m = _PREFIX_PATTERN.match(text)
    if m:
        return text[m.end():].strip()
    return text


def detect_numbering_type(prefix: str) -> str | None:
    """Detect numbering type from a prefix string."""
    prefix = prefix.strip().rstrip(".")
    if not prefix:
        return None
    if re.match(r"^[IVXLCDM]+$", prefix, re.IGNORECASE):
        return "roman"
    if re.match(r"^[A-Z]$", prefix, re.IGNORECASE):
        return "alpha"
    if re.match(r"^\d+$", prefix):
        return "arabic"
    return None
