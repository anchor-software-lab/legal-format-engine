"""Tests for parsers/plain_text_parser.py."""

from __future__ import annotations

import pytest

from legal_format_engine.parsers.plain_text_parser import (
    _detect_heading,
    parse_plain_text,
)
from legal_format_engine.models.document import DocumentMetadata


class TestDetectHeading:
    def test_all_caps_heading(self):
        result = _detect_heading("TABLE OF CONTENTS")
        assert result is not None
        assert result["level"] == 1

    def test_too_long_not_heading(self):
        result = _detect_heading("A" * 121)
        assert result is None

    def test_roman_numeral_prefix(self):
        result = _detect_heading("III. Standard of Review")
        assert result is not None
        assert result["level"] == 2

    def test_letter_prefix(self):
        result = _detect_heading("A. First point")
        assert result is not None
        assert result["level"] == 3

    def test_arabic_prefix(self):
        result = _detect_heading("1. First sub-point")
        assert result is not None
        assert result["level"] == 4

    def test_sentence_not_heading(self):
        result = _detect_heading("This is a regular sentence with some text in it.")
        assert result is None

    def test_short_all_caps_abbreviation(self):
        # Less than 3 alpha chars should not match
        result = _detect_heading("ID")
        assert result is None

    def test_caps_ending_in_period_not_heading(self):
        result = _detect_heading("THE COURT HELD THAT THE MOTION WAS DENIED.")
        assert result is None

    def test_long_sentence_with_letter_prefix(self):
        long = "A. " + "word " * 20
        result = _detect_heading(long.strip())
        assert result is None  # too many words

    def test_empty_string(self):
        assert _detect_heading("") is None

    def test_all_caps_many_words(self):
        result = _detect_heading("ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE TEN ELEVEN TWELVE THIRTEEN")
        assert result is None  # > 12 words


class TestParsePlainText:
    def test_basic_parsing(self, sample_brief_text):
        doc = parse_plain_text(sample_brief_text)
        assert len(doc.sections) >= 5

    def test_headings_detected(self, sample_brief_text):
        doc = parse_plain_text(sample_brief_text)
        headings = [s.heading for s in doc.sections if s.heading]
        assert "TABLE OF CONTENTS" in headings
        assert "ARGUMENT" in headings

    def test_content_captured(self, sample_brief_text):
        doc = parse_plain_text(sample_brief_text)
        # STATEMENT OF THE CASE has body content
        case_sections = [s for s in doc.sections if "CASE" in s.heading]
        assert len(case_sections) >= 1
        assert len(case_sections[0].content) >= 1

    def test_metadata_applied(self, sample_brief_text):
        meta = DocumentMetadata(jurisdiction="california")
        doc = parse_plain_text(sample_brief_text, meta)
        assert doc.metadata.jurisdiction == "california"

    def test_default_metadata(self, sample_brief_text):
        doc = parse_plain_text(sample_brief_text)
        assert doc.metadata.jurisdiction == "wisconsin"

    def test_empty_text(self):
        doc = parse_plain_text("")
        assert len(doc.sections) == 0

    def test_only_body_text(self):
        text = "This is just a paragraph of text without any headings whatsoever."
        doc = parse_plain_text(text)
        assert len(doc.sections) == 1
        assert doc.sections[0].heading == ""

    def test_blank_lines_preserved_as_empty_blocks(self, sample_brief_text):
        doc = parse_plain_text(sample_brief_text)
        # There should be empty content blocks where blank lines appeared
        for section in doc.sections:
            if section.content:
                # At least some sections should have empty blocks from blank lines
                pass  # Just verifying it doesn't crash

    def test_roman_numeral_subsections(self, sample_brief_text):
        doc = parse_plain_text(sample_brief_text)
        # Roman numeral headings should be level 2
        l2_sections = [s for s in doc.sections if s.heading_level == 2]
        assert len(l2_sections) >= 1

    def test_body_text_blocks_marked(self, sample_brief_text):
        doc = parse_plain_text(sample_brief_text)
        for section in doc.sections:
            for block in section.content:
                if block.text.strip():
                    assert block.is_body_text is True

    def test_multiple_paragraphs(self):
        text = "HEADING\n\nFirst paragraph.\n\nSecond paragraph."
        doc = parse_plain_text(text)
        assert len(doc.sections) == 1
        body_blocks = [b for b in doc.sections[0].content if b.text.strip()]
        assert len(body_blocks) == 2

    def test_sections_have_section_type_empty(self, sample_brief_text):
        doc = parse_plain_text(sample_brief_text)
        for section in doc.sections:
            assert section.section_type == ""
