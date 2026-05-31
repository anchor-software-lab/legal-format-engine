"""PDF text extraction for corpus bootstrap.

pdfplumber handles multi-column briefs better than pdfminer.six;
both are pure-Python so they work in CI without poppler.

`extract_text(pdf_bytes)` returns one whole-document string with
page boundaries marked by `\f` (form feed) so downstream callers
can attribute citations to page numbers.

`surrounding_text(text, start, end, window=200)` is the helper the
extractor uses to grab context around each citation eyecite found.
"""

from __future__ import annotations

import io
from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int  # 1-indexed
    text: str
    char_offset: int  # offset of this page's text within the whole-document string


@dataclass(frozen=True)
class ExtractedPDF:
    text: str  # whole document; pages joined with \f
    pages: tuple[ExtractedPage, ...]


def extract_text(pdf_bytes: bytes) -> ExtractedPDF:
    """Extract text from a PDF.

    Returns the whole-document text concatenated with `\\f` between
    pages, plus a tuple of per-page records mapping page number to
    its char-offset inside the whole document.
    """
    import pdfplumber  # noqa: PLC0415 — heavy import, kept local

    pages: list[ExtractedPage] = []
    pieces: list[str] = []
    offset = 0
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            extracted = page.extract_text() or ""
            pages.append(
                ExtractedPage(
                    page_number=idx,
                    text=extracted,
                    char_offset=offset,
                )
            )
            pieces.append(extracted)
            offset += len(extracted) + 1  # +1 for the page separator below
    whole = "\f".join(pieces)
    return ExtractedPDF(text=whole, pages=tuple(pages))


# Sentence-boundary heuristic for Bluebook-dense legal prose:
#   1. Candidate boundary = `<punct>` + space + Capital + lowercase.
#   2. Reject if the preceding word (text up to the punct) is in a
#      known legal-abbreviation list. This is what stops "v. Holiday"
#      and "Stat. § 802" from looking like sentence ends.
import re as _re

_SENT_END = _re.compile(r"[.;?!] (?=[A-Z][a-z])")

# Common legal abbreviations that end in a period. Includes both case
# titles (v., vs.) and reporter / signal abbreviations (Wis., U.S., F.,
# Stat., e.g.). Single-letter forms are intentionally here — they're
# the worst false-positives in citation-dense text.
_ABBREVIATIONS = frozenset({
    "v.", "vs.", "Inc.", "Co.", "Corp.", "Ltd.", "LLC.", "LLP.", "L.L.C.",
    "Mr.", "Mrs.", "Ms.", "Dr.", "Hon.", "Prof.",
    "St.", "Ave.", "Blvd.", "Rd.", "No.",
    "Wis.", "U.S.", "F.", "S.", "N.", "E.", "W.", "P.", "A.",
    "Stat.", "Const.", "art.", "amend.",
    "L.", "Ed.", "Ct.", "Cir.", "App.", "Dist.", "Sup.", "Cong.",
    "Cf.", "cf.", "e.g.", "i.e.", "etc.", "Id.", "id.", "Et.",
    "al.", "Jan.", "Feb.", "Mar.", "Apr.", "Jun.", "Jul.", "Aug.",
    "Sept.", "Oct.", "Nov.", "Dec.",
})


def _is_real_sentence_end(text: str, punct_pos: int) -> bool:
    """True iff the word ending at `punct_pos` isn't a known abbreviation."""
    # Walk back to the start of the word (run of non-space chars
    # ending at the punct). Include the punct in the word.
    word_end = punct_pos + 1  # inclusive of the punct
    i = word_end - 1
    while i > 0 and not text[i - 1].isspace():
        i -= 1
    word = text[i:word_end]
    return word not in _ABBREVIATIONS


def surrounding_text(
    text: str, start: int, end: int, *, window: int = 200
) -> str:
    """Return ~`window` chars on each side of `[start, end]`, trimmed
    to the nearest non-abbreviation sentence boundary on each side."""
    lo = max(0, start - window)
    hi = min(len(text), end + window)
    chunk = text[lo:hi]
    cite_in_chunk_end = end - lo

    # Leading trim: walk all candidate boundaries, keep the rightmost
    # one that isn't a legal abbreviation.
    last_end = -1
    leading = chunk[: end - lo]
    for m in _SENT_END.finditer(leading):
        if _is_real_sentence_end(chunk, m.start()):
            last_end = m.end()
    if last_end > 0:
        chunk = chunk[last_end:]
        cite_in_chunk_end -= last_end

    # Trailing trim: leftmost real boundary after the cite.
    for m in _SENT_END.finditer(chunk, cite_in_chunk_end):
        if _is_real_sentence_end(chunk, m.start()):
            chunk = chunk[: m.start() + 1]
            break

    return _normalize_whitespace(chunk)


def page_number_for_offset(pages: tuple[ExtractedPage, ...], offset: int) -> int:
    """Locate the page whose char range contains `offset`."""
    page_no = 1
    for page in pages:
        if offset >= page.char_offset:
            page_no = page.page_number
    return page_no


def _normalize_whitespace(s: str) -> str:
    # Briefs often have hyphenated line breaks; collapse them.
    s = s.replace("-\n", "")
    return " ".join(s.split())
