"""Tests for plain text parser."""

from legal_format_engine.models.document import HeadingLevel
from legal_format_engine.parsers.plain_text_parser import parse_plain_text


class TestPlainTextParser:
    def test_detects_sections(self, sample_brief_text):
        doc = parse_plain_text(sample_brief_text)
        assert len(doc.sections) > 0
        headings = [s.heading_text for s in doc.sections]
        assert "STATEMENT OF ISSUES" in headings
        assert "ARGUMENT" in headings
        assert "CONCLUSION" in headings

    def test_detects_level_1(self, sample_brief_text):
        doc = parse_plain_text(sample_brief_text)
        # ALL CAPS sections should be Level 1
        issues = next(s for s in doc.sections if s.heading_text == "STATEMENT OF ISSUES")
        assert issues.heading_level == HeadingLevel.LEVEL_1

    def test_preserves_content(self, sample_brief_text):
        doc = parse_plain_text(sample_brief_text)
        facts = next(s for s in doc.sections if "FACTS" in s.heading_text)
        assert len(facts.content) > 0
        all_text = " ".join(b.text for b in facts.content)
        assert "Officer James Rodriguez" in all_text

    def test_preserves_raw_text(self, sample_brief_text):
        doc = parse_plain_text(sample_brief_text)
        assert doc.raw_text == sample_brief_text

    def test_empty_input(self):
        doc = parse_plain_text("")
        assert doc.sections == []

    def test_no_headings(self):
        doc = parse_plain_text("Just some plain text without any headings.\nMore text here.")
        # Should create a preamble or no sections
        assert len(doc.sections) <= 1
