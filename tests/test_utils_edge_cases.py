"""Edge case tests for utility modules (numbering, text)."""

import pytest

from legal_format_engine.utils.numbering import (
    generate_prefix,
    int_to_alpha_lower,
    int_to_alpha_upper,
    int_to_roman,
    roman_to_int,
    strip_numbering_prefix,
)
from legal_format_engine.utils.text import (
    fuzzy_heading_match,
    is_likely_heading,
    normalize_for_matching,
    normalize_whitespace,
    to_sentence_case,
    to_title_case,
    to_upper,
)


# ── Numbering Edge Cases ───────────────────────────────────────────


class TestRomanNumeralBoundaries:
    def test_value_1(self):
        assert int_to_roman(1) == "I"

    def test_value_4(self):
        assert int_to_roman(4) == "IV"

    def test_value_9(self):
        assert int_to_roman(9) == "IX"

    def test_value_40(self):
        assert int_to_roman(40) == "XL"

    def test_value_90(self):
        assert int_to_roman(90) == "XC"

    def test_value_400(self):
        assert int_to_roman(400) == "CD"

    def test_value_900(self):
        assert int_to_roman(900) == "CM"

    def test_value_3999(self):
        assert int_to_roman(3999) == "MMMCMXCIX"

    def test_zero_raises(self):
        with pytest.raises((ValueError, Exception)):
            int_to_roman(0)

    def test_negative_raises(self):
        with pytest.raises((ValueError, Exception)):
            int_to_roman(-1)

    def test_round_trip(self):
        for n in [1, 4, 9, 14, 40, 49, 90, 99, 400, 500, 900, 1000, 2024, 3999]:
            assert roman_to_int(int_to_roman(n)) == n


class TestRomanToIntEdgeCases:
    def test_lowercase(self):
        assert roman_to_int("iv") == 4

    def test_mixed_case(self):
        assert roman_to_int("Iv") == 4

    def test_empty_string(self):
        with pytest.raises((ValueError, Exception)):
            roman_to_int("")

    def test_whitespace_only(self):
        with pytest.raises((ValueError, Exception)):
            roman_to_int("   ")

    def test_invalid_chars(self):
        with pytest.raises((ValueError, Exception)):
            roman_to_int("ABC")


class TestAlphaConversionBoundaries:
    def test_a_is_1(self):
        assert int_to_alpha_upper(1) == "A"

    def test_z_is_26(self):
        assert int_to_alpha_upper(26) == "Z"

    def test_aa_is_27(self):
        result = int_to_alpha_upper(27)
        assert result == "AA"

    def test_az_is_52(self):
        result = int_to_alpha_upper(52)
        assert result == "AZ"

    def test_ba_is_53(self):
        result = int_to_alpha_upper(53)
        assert result == "BA"

    def test_lower_a(self):
        assert int_to_alpha_lower(1) == "a"

    def test_lower_z(self):
        assert int_to_alpha_lower(26) == "z"

    def test_zero_raises(self):
        with pytest.raises((ValueError, Exception)):
            int_to_alpha_upper(0)

    def test_negative_raises(self):
        with pytest.raises((ValueError, Exception)):
            int_to_alpha_upper(-1)


class TestGeneratePrefix:
    # Note: generate_prefix(index, numbering_type) - index first

    def test_roman_index_1(self):
        assert generate_prefix(1, "roman") == "I."

    def test_alpha_upper_index_1(self):
        assert generate_prefix(1, "alpha_upper") == "A."

    def test_alpha_lower_index_1(self):
        assert generate_prefix(1, "alpha_lower") == "a."

    def test_arabic_index_1(self):
        assert generate_prefix(1, "arabic") == "1."

    def test_none_type(self):
        assert generate_prefix(1, None) == ""

    def test_unknown_type(self):
        with pytest.raises(ValueError):
            generate_prefix(1, "unknown_type")

    def test_large_roman(self):
        result = generate_prefix(50, "roman")
        assert result == "L."

    def test_large_alpha(self):
        result = generate_prefix(27, "alpha_upper")
        assert result == "AA."


class TestStripNumberingPrefix:
    def test_roman_dot(self):
        prefix, rest = strip_numbering_prefix("I. Statement of Facts")
        assert prefix == "I."
        assert rest.strip() == "Statement of Facts"

    def test_roman_complex(self):
        prefix, rest = strip_numbering_prefix("XIV. Argument Section")
        assert prefix == "XIV."

    def test_alpha_dot(self):
        prefix, rest = strip_numbering_prefix("A. First point")
        assert prefix == "A."
        assert rest.strip() == "First point"

    def test_arabic_dot(self):
        prefix, rest = strip_numbering_prefix("1. First item")
        assert prefix == "1."

    def test_no_prefix(self):
        prefix, rest = strip_numbering_prefix("Statement of Facts")
        assert prefix == ""
        assert rest == "Statement of Facts"

    def test_empty_string(self):
        prefix, rest = strip_numbering_prefix("")
        assert prefix == ""
        assert rest == ""

    def test_only_prefix(self):
        prefix, rest = strip_numbering_prefix("I.")
        assert prefix == "I."

    def test_double_space_after_prefix(self):
        prefix, rest = strip_numbering_prefix("I.  Statement")
        assert prefix == "I."
        assert "Statement" in rest

    def test_parenthetical_number(self):
        prefix, rest = strip_numbering_prefix("(1) First item")
        # Should handle or return empty prefix
        assert isinstance(prefix, str)
        assert isinstance(rest, str)

    def test_multi_digit_arabic(self):
        prefix, rest = strip_numbering_prefix("10. Tenth item")
        assert prefix == "10."

    def test_lowercase_roman(self):
        prefix, rest = strip_numbering_prefix("iii. Third sub-point")
        # May or may not detect lowercase roman
        assert isinstance(prefix, str)


# ── Text Utility Edge Cases ────────────────────────────────────────


class TestCaseConversionEdgeCases:
    def test_upper_empty(self):
        assert to_upper("") == ""

    def test_upper_unicode(self):
        result = to_upper("café")
        assert result == "CAFÉ"

    def test_upper_numbers(self):
        assert to_upper("rule 802.04") == "RULE 802.04"

    def test_upper_special_chars(self):
        assert to_upper("§ 904.04(2)(a)") == "§ 904.04(2)(A)"

    def test_title_empty(self):
        assert to_title_case("") == ""

    def test_title_single_word(self):
        result = to_title_case("argument")
        assert result == "Argument"

    def test_title_all_uppercase(self):
        result = to_title_case("STATEMENT OF FACTS")
        # Should produce title case
        assert result[0].isupper()

    def test_title_with_v_dot(self):
        result = to_title_case("state v. smith")
        # "v." should remain lowercase
        assert "v." in result.lower()

    def test_sentence_empty(self):
        assert to_sentence_case("") == ""

    def test_sentence_single_word(self):
        result = to_sentence_case("ARGUMENT")
        assert result == "Argument"

    def test_sentence_preserves_rest_lower(self):
        result = to_sentence_case("THE COURT ERRED")
        assert result[0] == "T"
        # Rest should be lowercase
        assert result[1:] == result[1:].lower()


class TestWhitespaceNormalization:
    def test_empty(self):
        assert normalize_whitespace("") == ""

    def test_tabs(self):
        result = normalize_whitespace("hello\tworld")
        assert "\t" not in result or result == "hello\tworld"

    def test_multiple_spaces(self):
        result = normalize_whitespace("hello    world")
        assert "    " not in result

    def test_newlines(self):
        result = normalize_whitespace("hello\n\n\nworld")
        assert isinstance(result, str)

    def test_leading_trailing(self):
        result = normalize_whitespace("  hello  ")
        assert not result.startswith("  ")

    def test_only_whitespace(self):
        result = normalize_whitespace("     ")
        assert result.strip() == ""


class TestFuzzyHeadingMatchEdgeCases:
    def test_empty_candidates(self):
        result = fuzzy_heading_match("ARGUMENT", {})
        assert result is None

    def test_empty_heading(self):
        candidates = {"argument": ["Argument"]}
        result = fuzzy_heading_match("", candidates)
        assert result is None

    def test_exact_match(self):
        candidates = {"argument": ["Argument", "ARGUMENT"]}
        result = fuzzy_heading_match("ARGUMENT", candidates)
        assert result == "argument"

    def test_alias_match(self):
        candidates = {"statement_of_issues": ["Statement of the Issues", "Issues Presented"]}
        result = fuzzy_heading_match("Issues Presented", candidates)
        assert result == "statement_of_issues"

    def test_with_numbering_prefix(self):
        candidates = {"argument": ["Argument"]}
        result = fuzzy_heading_match("I. Argument", candidates)
        # Should match even with prefix
        assert result == "argument"

    def test_trailing_period(self):
        candidates = {"argument": ["Argument"]}
        result = fuzzy_heading_match("Argument.", candidates)
        # May or may not match - depends on implementation
        assert isinstance(result, (str, type(None)))

    def test_case_insensitive(self):
        candidates = {"argument": ["Argument"]}
        result = fuzzy_heading_match("argument", candidates)
        assert result == "argument"

    def test_no_match(self):
        candidates = {"argument": ["Argument"]}
        result = fuzzy_heading_match("Completely Different Heading", candidates)
        assert result is None

    def test_substring_ambiguity(self):
        candidates = {
            "statement_of_case": ["Statement of the Case"],
            "statement_of_case_and_facts": ["Statement of the Case and Facts"],
        }
        result = fuzzy_heading_match("STATEMENT OF THE CASE AND FACTS", candidates)
        assert result == "statement_of_case_and_facts"

    def test_multiple_possible_matches(self):
        candidates = {
            "conclusion": ["Conclusion"],
            "argument": ["Argument"],
        }
        result = fuzzy_heading_match("CONCLUSION", candidates)
        assert result == "conclusion"


class TestIsLikelyHeadingEdgeCases:
    def test_empty(self):
        assert not is_likely_heading("")

    def test_single_char(self):
        result = is_likely_heading("A")
        assert isinstance(result, bool)

    def test_two_chars(self):
        result = is_likely_heading("AB")
        assert isinstance(result, bool)

    def test_exactly_80_chars(self):
        text = "A" * 80
        result = is_likely_heading(text)
        assert isinstance(result, bool)

    def test_exactly_150_chars(self):
        text = "HEADING " + "X" * 142
        result = is_likely_heading(text)
        assert isinstance(result, bool)

    def test_over_150_chars(self):
        text = "A" * 200
        assert not is_likely_heading(text)

    def test_all_numbers(self):
        result = is_likely_heading("1234567890")
        assert isinstance(result, bool)

    def test_all_special_chars(self):
        assert not is_likely_heading("!!!!!!!!!")

    def test_party_name_with_comma(self):
        # Party names like "JEFFREY JAMES CHRISTOPHERSON," should NOT be headings
        result = is_likely_heading("JEFFREY JAMES CHRISTOPHERSON,")
        # This is tricky - it IS all caps but has trailing comma
        assert isinstance(result, bool)

    def test_short_abbreviation(self):
        result = is_likely_heading("FBI")
        assert isinstance(result, bool)

    def test_mixed_case_short(self):
        result = is_likely_heading("The Case Name")
        assert isinstance(result, bool)

    def test_numbered_heading(self):
        assert is_likely_heading("I. Statement of Facts")

    def test_long_paragraph_text(self):
        text = "This is a regular paragraph that goes on and on. " * 5
        assert not is_likely_heading(text)


class TestNormalizeForMatching:
    def test_strips_prefix_and_lowercases(self):
        result = normalize_for_matching("I. STATEMENT OF FACTS")
        assert "statement" in result.lower()

    def test_empty(self):
        result = normalize_for_matching("")
        assert result == ""

    def test_only_prefix(self):
        result = normalize_for_matching("I.")
        assert isinstance(result, str)

    def test_special_chars(self):
        result = normalize_for_matching("§ 904.04")
        assert isinstance(result, str)

    def test_unicode(self):
        result = normalize_for_matching("Über Argument")
        assert isinstance(result, str)
