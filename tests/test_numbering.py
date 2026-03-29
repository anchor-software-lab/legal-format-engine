"""Tests for numbering utilities."""

import pytest

from legal_format_engine.utils.numbering import (
    generate_prefix,
    int_to_alpha_upper,
    int_to_roman,
    roman_to_int,
    strip_numbering_prefix,
)


class TestIntToRoman:
    def test_basic_values(self):
        assert int_to_roman(1) == "I"
        assert int_to_roman(4) == "IV"
        assert int_to_roman(9) == "IX"
        assert int_to_roman(14) == "XIV"
        assert int_to_roman(42) == "XLII"

    def test_invalid(self):
        with pytest.raises(ValueError):
            int_to_roman(0)


class TestRomanToInt:
    def test_basic_values(self):
        assert roman_to_int("I") == 1
        assert roman_to_int("IV") == 4
        assert roman_to_int("XIV") == 14
        assert roman_to_int("xlii") == 42

    def test_invalid(self):
        with pytest.raises(ValueError):
            roman_to_int("IIII")


class TestIntToAlpha:
    def test_basic(self):
        assert int_to_alpha_upper(1) == "A"
        assert int_to_alpha_upper(2) == "B"
        assert int_to_alpha_upper(26) == "Z"
        assert int_to_alpha_upper(27) == "AA"


class TestGeneratePrefix:
    def test_roman(self):
        assert generate_prefix(1, "roman") == "I."
        assert generate_prefix(3, "roman") == "III."

    def test_alpha(self):
        assert generate_prefix(1, "alpha_upper") == "A."
        assert generate_prefix(2, "alpha_upper") == "B."

    def test_arabic(self):
        assert generate_prefix(1, "arabic") == "1."
        assert generate_prefix(10, "arabic") == "10."

    def test_none(self):
        assert generate_prefix(1, None) == ""


class TestStripPrefix:
    def test_roman(self):
        prefix, text = strip_numbering_prefix("I. Statement of Facts")
        assert prefix == "I."
        assert text == "Statement of Facts"

    def test_alpha(self):
        prefix, text = strip_numbering_prefix("A. Standard of Review")
        assert prefix == "A."
        assert text == "Standard of Review"

    def test_no_prefix(self):
        prefix, text = strip_numbering_prefix("ARGUMENT")
        assert prefix == ""
        assert text == "ARGUMENT"
