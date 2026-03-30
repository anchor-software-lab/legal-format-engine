"""Tests for the normalizer module."""

import pytest
from anchor_ml_engine.normalizer import (
    canonicalize_font_name,
    get_font_family_map,
    snap_font_size,
    snap_indent,
    snap_line_spacing,
    snap_margin,
    snap_to_standard,
    build_normalized_document,
    normalize_document,
    normalize_font_data,
    normalize_margins_data,
    normalize_headings_data,
)


class TestFontCanonicalization:
    """Test font name canonicalization."""

    def test_times_new_roman_variants(self):
        assert canonicalize_font_name("TimesNewRomanPSMT") == "Times New Roman"
        assert canonicalize_font_name("Times-Roman") == "Times New Roman"
        assert canonicalize_font_name("TimesNewRoman-Bold") == "Times New Roman"
        assert canonicalize_font_name("LiberationSerif") == "Times New Roman"
        assert canonicalize_font_name("NimbusRomNo9L") == "Times New Roman"

    def test_arial_helvetica_variants(self):
        assert canonicalize_font_name("ArialMT") == "Arial"
        assert canonicalize_font_name("Helvetica-Bold") == "Arial"
        assert canonicalize_font_name("HelveticaNeue") == "Arial"
        assert canonicalize_font_name("LiberationSans") == "Arial"

    def test_courier_variants(self):
        assert canonicalize_font_name("CourierNewPSMT") == "Courier New"
        assert canonicalize_font_name("Courier-Bold") == "Courier New"
        assert canonicalize_font_name("Consolas") == "Courier New"
        assert canonicalize_font_name("Menlo") == "Courier New"

    def test_century_schoolbook(self):
        assert canonicalize_font_name("CenturySchoolbook-Bold") == "Century Schoolbook"
        assert canonicalize_font_name("NewCenturySchlbk") == "Century Schoolbook"

    def test_garamond(self):
        assert canonicalize_font_name("EBGaramond") == "Garamond"
        assert canonicalize_font_name("AGaramondPro-Regular") == "Garamond"

    def test_book_antiqua(self):
        assert canonicalize_font_name("PalatinoLinotype") == "Book Antiqua"
        assert canonicalize_font_name("BookAntiqua-Bold") == "Book Antiqua"

    def test_georgia(self):
        assert canonicalize_font_name("Georgia-Bold") == "Georgia"

    def test_unknown_font_returned_as_is(self):
        assert canonicalize_font_name("MyCustomFont") == "MyCustomFont"
        assert canonicalize_font_name("FancyScript-Regular") == "FancyScript-Regular"

    def test_case_insensitive(self):
        assert canonicalize_font_name("TIMESNEWROMANPSMT") == "Times New Roman"
        assert canonicalize_font_name("arial") == "Arial"

    def test_font_family_map_not_empty(self):
        fmap = get_font_family_map()
        assert len(fmap) > 50


class TestMeasurementSnapping:
    """Test measurement snapping functions."""

    def test_snap_margin_to_one_inch(self):
        assert snap_margin(0.97) == 1.0
        assert snap_margin(1.03) == 1.0
        assert snap_margin(1.0) == 1.0

    def test_snap_margin_to_half_inch(self):
        assert snap_margin(0.48) == 0.5

    def test_snap_margin_not_within_tolerance(self):
        # 3.5 is not within 0.12 of any standard margin
        result = snap_margin(3.5)
        assert result == 3.5

    def test_snap_font_size_12(self):
        assert snap_font_size(11.8) == 12.0
        assert snap_font_size(12.2) == 12.0
        assert snap_font_size(12.0) == 12.0

    def test_snap_font_size_various(self):
        assert snap_font_size(10.0) == 10.0
        assert snap_font_size(14.0) == 14.0
        assert snap_font_size(10.3) == 10.5  # within 0.7 of 10.5

    def test_snap_line_spacing(self):
        assert snap_line_spacing(1.95) == 2.0
        assert snap_line_spacing(2.0) == 2.0
        assert snap_line_spacing(1.48) == 1.5

    def test_snap_indent(self):
        assert snap_indent(0.49) == 0.5
        assert snap_indent(0.0) == 0.0
        assert snap_indent(0.26) == 0.25

    def test_snap_to_standard_generic(self):
        standards = [1.0, 2.0, 3.0]
        assert snap_to_standard(1.05, standards, tolerance=0.15) == 1.0
        assert snap_to_standard(1.5, standards, tolerance=0.15) == 1.5  # not within tolerance


class TestNormalizeFontData:
    def test_empty_fonts(self):
        primary, secondary = normalize_font_data([])
        assert primary is None
        assert secondary == []

    def test_single_font(self):
        primary, secondary = normalize_font_data([
            {"font_name": "TimesNewRomanPSMT", "font_size_pt": 11.8}
        ])
        assert primary is not None
        assert primary.family == "Times New Roman"
        assert primary.size_pt == 12.0
        assert secondary == []

    def test_multiple_fonts(self):
        primary, secondary = normalize_font_data([
            {"font_name": "Arial", "font_size_pt": 12.0},
            {"font_name": "Courier", "font_size_pt": 10.0},
        ])
        assert primary.family == "Arial"
        assert len(secondary) == 1
        assert secondary[0].family == "Courier New"


class TestNormalizeMarginsData:
    def test_docx_margins(self):
        margins = normalize_margins_data(
            {"top": 0.97, "bottom": 1.03, "left": 1.0, "right": 1.0},
            source_format="docx",
        )
        assert margins is not None
        assert margins.top == 1.0
        assert margins.source_quality == "exact"

    def test_pdf_margins(self):
        margins = normalize_margins_data(
            {"top": 0.97, "bottom": 1.03, "left": 1.0, "right": 1.0},
            source_format="pdf",
        )
        assert margins.source_quality == "estimated"

    def test_empty_margins(self):
        assert normalize_margins_data({}) is None


class TestNormalizeHeadingsData:
    def test_headings_with_font_snapping(self):
        headings = normalize_headings_data([
            {"level": 1, "case_style": "upper", "alignment": "center",
             "bold": True, "font_size_pt": 13.8},
        ])
        assert len(headings) == 1
        assert headings[0].font_size_pt == 14.0


class TestBuildNormalizedDocument:
    def test_basic_build(self):
        doc = build_normalized_document(
            source_filename="test.docx",
            source_format="docx",
            fonts=[{"font_name": "Arial", "font_size_pt": 12.0}],
            margins={"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0},
            line_spacing=2.0,
            body_indent=0.5,
        )
        assert doc.source_filename == "test.docx"
        assert doc.primary_font.family == "Arial"
        assert doc.margins.top == 1.0
        assert doc.line_spacing == 2.0
        assert doc.body_first_line_indent == 0.5
        assert doc.extraction_confidence == 1.0


class TestNormalizeDocument:
    def test_normalize_unknown_format(self):
        doc = normalize_document(
            "/tmp/nonexistent.docx",
            category="test",
        )
        assert doc.source_format == "docx"
        assert doc.category == "test"
        assert doc.extraction_confidence == 1.0
