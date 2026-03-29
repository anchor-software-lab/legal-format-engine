"""Tests for PDF parser.

Note: Creating test PDFs programmatically via PyMuPDF (fitz).
"""

import tempfile
from pathlib import Path

import fitz  # PyMuPDF
import pytest

from legal_format_engine.parsers.pdf_parser import extract_pdf_format_profile, parse_pdf


def _create_sample_pdf() -> Path:
    """Create a minimal PDF brief for testing."""
    doc = fitz.open()

    # Page 1: Caption + TOC
    page = doc.new_page(width=612, height=792)  # 8.5x11 at 72dpi
    y = 72  # 1 inch from top

    # Centered heading
    page.insert_text(
        (200, y), "STATE OF WISCONSIN",
        fontsize=12, fontname="Times-Roman",
    )
    y += 24
    page.insert_text(
        (210, y), "COURT OF APPEALS",
        fontsize=12, fontname="Times-Roman",
    )
    y += 48
    page.insert_text(
        (72, y), "STATEMENT OF ISSUES",
        fontsize=12, fontname="Times-Bold",
    )
    y += 24
    page.insert_text(
        (72, y), "Whether the court erred in admitting evidence.",
        fontsize=12, fontname="Times-Roman",
    )

    # Page 2: Argument
    page2 = doc.new_page(width=612, height=792)
    y = 72
    page2.insert_text(
        (72, y), "ARGUMENT",
        fontsize=12, fontname="Times-Bold",
    )
    y += 24
    page2.insert_text(
        (72, y), "The circuit court clearly erred because the evidence was",
        fontsize=12, fontname="Times-Roman",
    )
    y += 18
    page2.insert_text(
        (72, y), "not probative and was substantially outweighed by prejudice.",
        fontsize=12, fontname="Times-Roman",
    )
    y += 36
    page2.insert_text(
        (72, y), "CONCLUSION",
        fontsize=12, fontname="Times-Bold",
    )
    y += 24
    page2.insert_text(
        (72, y), "For these reasons, this Court should reverse the judgment.",
        fontsize=12, fontname="Times-Roman",
    )

    path = Path(tempfile.mktemp(suffix=".pdf"))
    doc.save(str(path))
    doc.close()
    return path


class TestPdfParser:
    def test_parse_basic(self):
        path = _create_sample_pdf()
        doc = parse_pdf(path)
        assert len(doc.sections) > 0
        assert doc.raw_text is not None

    def test_detects_headings(self):
        path = _create_sample_pdf()
        doc = parse_pdf(path)
        headings = [s.heading_text for s in doc.sections]
        assert any("ARGUMENT" in h for h in headings)
        assert any("CONCLUSION" in h for h in headings)

    def test_preserves_content(self):
        path = _create_sample_pdf()
        doc = parse_pdf(path)
        all_text = doc.raw_text or ""
        assert "erred" in all_text

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_pdf("/nonexistent/file.pdf")

    def test_page_dimensions(self):
        path = _create_sample_pdf()
        profile = extract_pdf_format_profile(path)
        assert profile["page"]["width_inches"] == 8.5
        assert profile["page"]["height_inches"] == 11.0

    def test_detects_fonts(self):
        path = _create_sample_pdf()
        profile = extract_pdf_format_profile(path)
        assert "fonts" in profile
        assert profile["fonts"]["dominant"] != "Unknown"

    def test_detects_font_size(self):
        path = _create_sample_pdf()
        profile = extract_pdf_format_profile(path)
        assert profile["font_sizes"]["dominant_pt"] == 12.0
