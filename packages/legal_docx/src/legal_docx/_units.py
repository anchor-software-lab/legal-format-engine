"""Unit conversions used throughout docx parsing.

Word stores most measurements in twips (1/1440 inch) for layout and
half-points for font sizes. These helpers centralize the conversions so
parsers don't sprinkle magic numbers.
"""

from __future__ import annotations

TWIPS_PER_INCH = 1440
HALF_POINTS_PER_POINT = 2
TWENTIETHS_PER_LINE = 240  # `w:spacing line` is in 1/240ths of a line


def twips_to_inches(twips: int | float | None) -> float | None:
    if twips is None:
        return None
    return float(twips) / TWIPS_PER_INCH


def half_points_to_points(half_points: int | float | None) -> float | None:
    if half_points is None:
        return None
    return float(half_points) / HALF_POINTS_PER_POINT


def line_spacing_to_multiple(
    line: int | float | None, line_rule: str | None
) -> float | None:
    """Convert Word's `w:spacing line` to a line-spacing multiplier.

    Word stores line spacing as:
      - lineRule="auto"   → `line` is in 240ths of a line (240 = single,
        480 = double).
      - lineRule="exact"  → `line` is in twentieths of a point (exact
        height); we return None because this isn't a multiplier.
      - lineRule="atLeast" → minimum height in twentieths; also not a
        multiplier.
    """
    if line is None:
        return None
    rule = (line_rule or "auto").lower()
    if rule != "auto":
        return None
    return float(line) / TWENTIETHS_PER_LINE
