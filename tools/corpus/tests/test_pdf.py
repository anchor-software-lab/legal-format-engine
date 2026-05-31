"""Tests for PDF text extraction + the context-window helper."""

from __future__ import annotations

from tools.corpus.pdf import (
    ExtractedPage,
    page_number_for_offset,
    surrounding_text,
)


def test_surrounding_text_returns_window_around_span():
    text = (
        "The trial court erred. We review summary judgment de novo. "
        "See Tews v. NHI, LLC, 2010 WI 137. The standard is well-known."
    )
    cite_start = text.index("Tews")
    cite_end = text.index(", 2010") + len(", 2010")
    ctx = surrounding_text(text, cite_start, cite_end, window=80)
    assert "Tews" in ctx
    # Trims to sentence boundary.
    assert ctx.startswith("See") or ctx.startswith("We review")


def test_surrounding_text_collapses_whitespace_and_hyphens():
    text = "We hold that the case of Tews v. NHI,\nLLC governs.  See ¶ 4."
    ctx = surrounding_text(text, 18, 35, window=200)
    assert "  " not in ctx
    assert "Tews v. NHI, LLC" in ctx


def test_page_number_for_offset_finds_correct_page():
    pages = (
        ExtractedPage(page_number=1, text="A" * 100, char_offset=0),
        ExtractedPage(page_number=2, text="B" * 100, char_offset=101),
        ExtractedPage(page_number=3, text="C" * 100, char_offset=202),
    )
    assert page_number_for_offset(pages, 0) == 1
    assert page_number_for_offset(pages, 100) == 1
    assert page_number_for_offset(pages, 150) == 2
    assert page_number_for_offset(pages, 250) == 3


def test_page_number_falls_back_to_first_when_no_pages():
    assert page_number_for_offset((), 50) == 1
