"""Bluebook citation parsing, normalization, validation.

v0 surface:
- `parser.extract_citations_in_text(text, segment_id)` — eyecite-backed
  extraction returning normalized Citation records with signal context.
- `bluebook.signal` — T.1.4 signal taxonomy + lookback detection.
- `checkers.BluebookSignalChecker` — flags signals not in T.1.4.
- `checkers.PinpointMissingChecker` — flags full case cites with no pinpoint.

Coming after v0: Bluebook case-form normalizer (Rule 10), short-form
resolver, id/supra chain validation, quote-accuracy LLM checker.
"""

from legal_citations.parser import (
    ExtractedCitation,
    all_citations,
    extract_citations_in_text,
)
from legal_citations.checkers import (
    BLUEBOOK_PINPOINT_ID,
    BLUEBOOK_SIGNAL_ID,
    BluebookSignalChecker,
    PinpointMissingChecker,
    build_pinpoint_checker,
    build_signal_checker,
    get_or_extract_citations,
)
from legal_citations.bluebook.signal import (
    SIGNALS,
    SignalKind,
    classify_signal_text,
    find_signal_before,
)
from legal_citations.bluebook.case_form import (
    BLUEBOOK_CASE_FORM_ID,
    BluebookCaseFormChecker,
    NormalizeCaseOutput,
    build_case_form_checker,
)

__all__ = [
    "BLUEBOOK_CASE_FORM_ID",
    "BLUEBOOK_PINPOINT_ID",
    "BLUEBOOK_SIGNAL_ID",
    "BluebookCaseFormChecker",
    "BluebookSignalChecker",
    "ExtractedCitation",
    "NormalizeCaseOutput",
    "PinpointMissingChecker",
    "SIGNALS",
    "SignalKind",
    "all_citations",
    "build_case_form_checker",
    "build_pinpoint_checker",
    "build_signal_checker",
    "classify_signal_text",
    "extract_citations_in_text",
    "find_signal_before",
    "get_or_extract_citations",
]
