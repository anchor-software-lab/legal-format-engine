"""Tests for text and numbering utilities."""

from __future__ import annotations

import pytest

from legal_format_engine.utils.text import (
    fuzzy_heading_match,
    is_all_caps,
    normalize_heading,
    normalize_whitespace,
    remove_diacritics,
    strip_non_ascii,
    to_all_caps,
    to_sentence_case,
    to_title_case,
)
from legal_format_engine.utils.numbering import (
    detect_numbering_type,
    from_roman,
    generate_prefix,
    strip_numbering_prefix,
    to_alpha,
    to_roman,
)


# ── normalize_whitespace ───────────────────────────────────────────────────

class TestNormalizeWhitespace:
    def test_collapses_spaces(self):
        assert normalize_whitespace("a  b   c") == "a b c"

    def test_strips_leading_trailing(self):
        assert normalize_whitespace("  hello  ") == "hello"

    def test_tabs_and_newlines(self):
        assert normalize_whitespace("a\t\nb") == "a b"

    def test_empty(self):
        assert normalize_whitespace("") == ""

    def test_single_space(self):
        assert normalize_whitespace(" ") == ""


# ── normalize_heading ──────────────────────────────────────────────────────

class TestNormalizeHeading:
    def test_lowercases(self):
        assert normalize_heading("ARGUMENT") == "argument"

    def test_strips_roman_prefix(self):
        assert normalize_heading("III. Standard of Review") == "standard of review"

    def test_strips_letter_prefix(self):
        assert normalize_heading("A. First Point") == "first point"

    def test_strips_arabic_prefix(self):
        assert normalize_heading("1. First Point") == "first point"

    def test_strips_punctuation(self):
        assert normalize_heading("Statement of the Case.") == "statement of the case"

    def test_empty(self):
        assert normalize_heading("") == ""


# ── is_all_caps ────────────────────────────────────────────────────────────

class TestIsAllCaps:
    def test_all_caps(self):
        assert is_all_caps("ARGUMENT") is True

    def test_mixed(self):
        assert is_all_caps("Argument") is False

    def test_with_spaces_and_punctuation(self):
        assert is_all_caps("TABLE OF CONTENTS") is True

    def test_no_alpha(self):
        assert is_all_caps("123") is False

    def test_empty(self):
        assert is_all_caps("") is False


# ── to_all_caps ────────────────────────────────────────────────────────────

class TestToAllCaps:
    def test_basic(self):
        assert to_all_caps("hello world") == "HELLO WORLD"

    def test_already_caps(self):
        assert to_all_caps("HELLO") == "HELLO"


# ── to_title_case ──────────────────────────────────────────────────────────

class TestToTitleCase:
    def test_basic(self):
        assert to_title_case("statement of the case") == "Statement of the Case"

    def test_first_word_always_capitalized(self):
        assert to_title_case("the argument") == "The Argument"

    def test_minor_words_lowercase(self):
        result = to_title_case("position on oral argument and publication")
        assert result == "Position on Oral Argument and Publication"

    def test_single_word(self):
        assert to_title_case("argument") == "Argument"

    def test_all_caps_input(self):
        result = to_title_case("TABLE OF CONTENTS")
        assert result == "Table of Contents"

    def test_empty(self):
        assert to_title_case("") == ""


# ── to_sentence_case ──────────────────────────────────────────────────────

class TestToSentenceCase:
    def test_basic(self):
        assert to_sentence_case("HELLO WORLD") == "Hello world"

    def test_empty(self):
        assert to_sentence_case("") == ""

    def test_single_char(self):
        assert to_sentence_case("a") == "A"


# ── fuzzy_heading_match ───────────────────────────────────────────────────

class TestFuzzyHeadingMatch:
    @pytest.fixture()
    def candidates(self):
        return {
            "argument": ["Argument", "Arguments"],
            "conclusion": ["Conclusion", "Prayer for Relief"],
            "statement_of_issues": ["Issues Presented", "Statement of the Issues"],
            "table_of_contents": ["Table of Contents", "Contents", "TOC"],
        }

    def test_exact_match(self, candidates):
        assert fuzzy_heading_match("Argument", candidates) == "argument"

    def test_case_insensitive(self, candidates):
        assert fuzzy_heading_match("ARGUMENT", candidates) == "argument"

    def test_alias_match(self, candidates):
        assert fuzzy_heading_match("Prayer for Relief", candidates) == "conclusion"

    def test_prefix_stripped(self, candidates):
        assert fuzzy_heading_match("I. Argument", candidates) == "argument"

    def test_substring_match(self, candidates):
        assert fuzzy_heading_match("Issues Presented for Review", candidates) == "statement_of_issues"

    def test_no_match(self, candidates):
        assert fuzzy_heading_match("Appendix", candidates) is None

    def test_empty_heading(self, candidates):
        assert fuzzy_heading_match("", candidates) is None

    def test_whitespace_only(self, candidates):
        assert fuzzy_heading_match("   ", candidates) is None

    def test_toc_alias(self, candidates):
        assert fuzzy_heading_match("TOC", candidates) == "table_of_contents"


# ── strip_non_ascii ────────────────────────────────────────────────────────

class TestStripNonAscii:
    def test_ascii_unchanged(self):
        assert strip_non_ascii("hello") == "hello"

    def test_removes_unicode(self):
        assert strip_non_ascii("hello\u2019world") == "helloworld"

    def test_section_symbol(self):
        assert strip_non_ascii("Wis. Stat. \u00a7 809") == "Wis. Stat.  809"


# ── remove_diacritics ─────────────────────────────────────────────────────

class TestRemoveDiacritics:
    def test_accented_chars(self):
        assert remove_diacritics("caf\u00e9") == "cafe"

    def test_plain_text(self):
        assert remove_diacritics("hello") == "hello"

    def test_umlaut(self):
        assert remove_diacritics("\u00fc") == "u"


# ── to_roman ───────────────────────────────────────────────────────────────

class TestToRoman:
    @pytest.mark.parametrize("n,expected", [
        (1, "I"), (2, "II"), (3, "III"), (4, "IV"), (5, "V"),
        (9, "IX"), (10, "X"), (14, "XIV"), (40, "XL"), (50, "L"),
        (90, "XC"), (100, "C"), (400, "CD"), (500, "D"), (900, "CM"),
        (1000, "M"), (1999, "MCMXCIX"),
    ])
    def test_conversions(self, n, expected):
        assert to_roman(n) == expected

    def test_zero(self):
        assert to_roman(0) == ""

    def test_negative(self):
        assert to_roman(-1) == ""


# ── from_roman ─────────────────────────────────────────────────────────────

class TestFromRoman:
    @pytest.mark.parametrize("s,expected", [
        ("I", 1), ("IV", 4), ("IX", 9), ("XIV", 14), ("XL", 40),
        ("XCIX", 99), ("CD", 400), ("MCMXCIX", 1999),
    ])
    def test_conversions(self, s, expected):
        assert from_roman(s) == expected

    def test_lowercase(self):
        assert from_roman("iv") == 4

    def test_whitespace(self):
        assert from_roman("  X  ") == 10


# ── to_alpha ───────────────────────────────────────────────────────────────

class TestToAlpha:
    def test_a_through_z(self):
        assert to_alpha(1) == "A"
        assert to_alpha(26) == "Z"

    def test_lowercase(self):
        assert to_alpha(1, upper=False) == "a"

    def test_out_of_range(self):
        assert to_alpha(0) == ""
        assert to_alpha(27) == ""


# ── generate_prefix ───────────────────────────────────────────────────────

class TestGeneratePrefix:
    def test_roman(self):
        assert generate_prefix(1, "roman") == "I."
        assert generate_prefix(4, "roman") == "IV."

    def test_alpha(self):
        assert generate_prefix(1, "alpha") == "A."
        assert generate_prefix(3, "alpha") == "C."

    def test_arabic(self):
        assert generate_prefix(1, "arabic") == "1."
        assert generate_prefix(10, "arabic") == "10."

    def test_none(self):
        assert generate_prefix(1, None) == ""

    def test_unknown(self):
        assert generate_prefix(1, "unknown") == ""


# ── strip_numbering_prefix ────────────────────────────────────────────────

class TestStripNumberingPrefix:
    def test_roman(self):
        assert strip_numbering_prefix("III. Argument") == "Argument"

    def test_alpha(self):
        assert strip_numbering_prefix("A. First Point") == "First Point"

    def test_arabic(self):
        assert strip_numbering_prefix("1. First Point") == "First Point"

    def test_no_prefix(self):
        assert strip_numbering_prefix("Argument") == "Argument"

    def test_empty(self):
        assert strip_numbering_prefix("") == ""


# ── detect_numbering_type ─────────────────────────────────────────────────

class TestDetectNumberingType:
    def test_roman(self):
        assert detect_numbering_type("III.") == "roman"
        assert detect_numbering_type("IV") == "roman"

    def test_alpha(self):
        assert detect_numbering_type("A.") == "alpha"
        assert detect_numbering_type("B") == "alpha"

    def test_arabic(self):
        assert detect_numbering_type("1.") == "arabic"
        assert detect_numbering_type("42") == "arabic"

    def test_empty(self):
        assert detect_numbering_type("") is None

    def test_unknown(self):
        assert detect_numbering_type("???") is None
