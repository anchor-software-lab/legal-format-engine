"""Checker implementations exposed by legal_format_engine.

Currently:
- `formatting_checker` — diffs `ObservedStyle` on each Segment against
  the resolved FormatSpec from `merge_with_rules`.
"""

from legal_format_engine.checkers.formatting_checker import (
    FORMATTING_SPEC_DIFF_ID,
    FormattingSpecDiffChecker,
    build_formatting_checker,
)

__all__ = [
    "FORMATTING_SPEC_DIFF_ID",
    "FormattingSpecDiffChecker",
    "build_formatting_checker",
]
