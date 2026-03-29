"""Tests for text utilities."""

from legal_format_engine.utils.text import (
    fuzzy_heading_match,
    is_likely_heading,
    normalize_for_matching,
    normalize_whitespace,
    to_sentence_case,
    to_title_case,
    to_upper,
)


class TestCaseConversions:
    def test_upper(self):
        assert to_upper("statement of facts") == "STATEMENT OF FACTS"

    def test_title_case(self):
        assert to_title_case("statement of the case") == "Statement of the Case"
        assert to_title_case("STATEMENT OF THE CASE") == "Statement of the Case"

    def test_sentence_case(self):
        assert to_sentence_case("STATEMENT OF FACTS") == "Statement of facts"

    def test_whitespace(self):
        assert normalize_whitespace("  hello   world  ") == "hello world"


class TestNormalizeForMatching:
    def test_strips_prefix(self):
        assert normalize_for_matching("I. STATEMENT OF THE CASE") == "statement of the case"

    def test_plain(self):
        assert normalize_for_matching("Statement of Facts") == "statement of facts"


class TestFuzzyMatch:
    def test_exact(self):
        aliases = {"statement_of_facts": ["Statement of Facts", "Facts"]}
        assert fuzzy_heading_match("STATEMENT OF FACTS", aliases) == "statement_of_facts"

    def test_alias(self):
        aliases = {"statement_of_facts": ["Statement of Facts", "Facts", "Factual Background"]}
        assert fuzzy_heading_match("Facts", aliases) == "statement_of_facts"

    def test_no_match(self):
        aliases = {"argument": ["Argument"]}
        assert fuzzy_heading_match("Preliminary Statement", aliases) is None

    def test_with_prefix(self):
        aliases = {"argument": ["Argument"]}
        assert fuzzy_heading_match("I. ARGUMENT", aliases) == "argument"


class TestIsLikelyHeading:
    def test_all_caps_short(self):
        assert is_likely_heading("STATEMENT OF FACTS") is True

    def test_long_paragraph(self):
        assert is_likely_heading("A" * 200) is False

    def test_numbered(self):
        assert is_likely_heading("I. Standard of Review") is True

    def test_empty(self):
        assert is_likely_heading("") is False
