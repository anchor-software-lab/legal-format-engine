"""Numbering conversion utilities for legal document headings."""

from __future__ import annotations

import re

ROMAN_VALUES = [
    (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
    (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
    (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
]

ROMAN_PATTERN = re.compile(
    r"^(M{0,3})(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$",
    re.IGNORECASE,
)

# Matches leading numbering prefixes: "I.", "II.", "A.", "1.", "a.", "(1)", "(a)"
NUMBERING_PREFIX_PATTERN = re.compile(
    r"^(?:"
    r"[IVXLC]+\.\s*"        # Roman: I., II., III.
    r"|[A-Z]\.\s*"           # Alpha upper: A., B., C.
    r"|[a-z]\.\s*"           # Alpha lower: a., b., c.
    r"|\d+\.\s*"             # Arabic: 1., 2., 3.
    r"|\(\d+\)\s*"           # Paren arabic: (1), (2)
    r"|\([a-z]\)\s*"         # Paren alpha: (a), (b)
    r")",
    re.IGNORECASE,
)


def int_to_roman(n: int) -> str:
    """Convert a positive integer to an uppercase Roman numeral string.

    >>> int_to_roman(1)
    'I'
    >>> int_to_roman(4)
    'IV'
    >>> int_to_roman(14)
    'XIV'
    """
    if n < 1:
        raise ValueError(f"Roman numerals must be positive, got {n}")
    result = []
    for value, numeral in ROMAN_VALUES:
        while n >= value:
            result.append(numeral)
            n -= value
    return "".join(result)


def roman_to_int(s: str) -> int:
    """Convert a Roman numeral string to an integer.

    >>> roman_to_int("IV")
    4
    >>> roman_to_int("xiv")
    14
    """
    s = s.upper().strip()
    if not s or not ROMAN_PATTERN.match(s):
        raise ValueError(f"Invalid Roman numeral: {s!r}")
    roman_map = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    for i, char in enumerate(s):
        val = roman_map[char]
        if i + 1 < len(s) and val < roman_map[s[i + 1]]:
            total -= val
        else:
            total += val
    return total


def int_to_alpha_upper(n: int) -> str:
    """Convert a 1-based index to uppercase letter(s).

    >>> int_to_alpha_upper(1)
    'A'
    >>> int_to_alpha_upper(26)
    'Z'
    >>> int_to_alpha_upper(27)
    'AA'
    """
    if n < 1:
        raise ValueError(f"Index must be positive, got {n}")
    result = []
    while n > 0:
        n -= 1
        result.append(chr(65 + (n % 26)))
        n //= 26
    return "".join(reversed(result))


def int_to_alpha_lower(n: int) -> str:
    """Convert a 1-based index to lowercase letter(s).

    >>> int_to_alpha_lower(1)
    'a'
    """
    return int_to_alpha_upper(n).lower()


def generate_prefix(index: int, numbering_type: str | None) -> str:
    """Generate a numbering prefix for a given 1-based index.

    Args:
        index: 1-based position among siblings.
        numbering_type: One of "roman", "alpha_upper", "alpha_lower", "arabic", or None.

    Returns:
        The prefix string (e.g., "I.", "A.", "1.") or empty string if no numbering.
    """
    if numbering_type is None:
        return ""
    match numbering_type:
        case "roman":
            return f"{int_to_roman(index)}."
        case "alpha_upper":
            return f"{int_to_alpha_upper(index)}."
        case "alpha_lower":
            return f"{int_to_alpha_lower(index)}."
        case "arabic":
            return f"{index}."
        case _:
            raise ValueError(f"Unknown numbering type: {numbering_type!r}")


def strip_numbering_prefix(text: str) -> tuple[str, str]:
    """Strip a leading numbering prefix from heading text.

    Returns:
        A tuple of (stripped_prefix, remaining_text).
        Returns ("", text) if no prefix is found.

    >>> strip_numbering_prefix("I. Statement of Facts")
    ('I.', 'Statement of Facts')
    >>> strip_numbering_prefix("ARGUMENT")
    ('', 'ARGUMENT')
    """
    if not text:
        return "", ""
    match = NUMBERING_PREFIX_PATTERN.match(text)
    if match:
        prefix = match.group().strip()
        remaining = text[match.end():].strip()
        return prefix, remaining
    return "", text.strip()
