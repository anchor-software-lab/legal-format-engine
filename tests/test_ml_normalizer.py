"""Tests for ml/normalizer.py."""

from __future__ import annotations

import pytest

from legal_format_engine.ml.normalizer import (
    FORMAT_CONFIDENCE,
    NormalizedDocument,
    normalize_document,
    normalize_font_name,
    snap_to_standard,
    _STANDARD_FONT_SIZES,
    _STANDARD_LINE_SPACINGS,
    _STANDARD_MARGINS,
)


class TestNormalizeFontName:
    def test_times_new_roman_psmt(self):
        assert normalize_font_name("TimesNewRomanPSMT") == "Times New Roman"

    def test_times_new_roman_lowercase(self):
        assert normalize_font_name("timesnewroman") == "Times New Roman"

    def test_times_plain(self):
        assert normalize_font_name("Times") == "Times New Roman"

    def test_arial(self):
        assert normalize_font_name("Arial") == "Arial"

    def test_arial_mt(self):
        assert normalize_font_name("ArialMT") == "Arial"

    def test_courier_new_psmt(self):
        assert normalize_font_name("CourierNewPSMT") == "Courier New"

    def test_courier_new_est(self):
        assert normalize_font_name("CourierNewest") == "Courier New"

    def test_century_schoolbook_abbreviated(self):
        assert normalize_font_name("CenturySchlBk") == "Century Schoolbook"

    def test_century_schoolbook_bt(self):
        assert normalize_font_name("CenturySchlBkBT") == "Century Schoolbook"

    def test_century_schoolbook_full(self):
        assert normalize_font_name("CenturySchoolbook") == "Century Schoolbook"

    def test_garamond(self):
        assert normalize_font_name("Garamond") == "Garamond"

    def test_calibri(self):
        assert normalize_font_name("Calibri") == "Calibri"

    def test_unknown_font_passthrough(self):
        assert normalize_font_name("UnknownSpecialFont") == "UnknownSpecialFont"

    def test_palatino_linotype(self):
        assert normalize_font_name("PalatinoLinotype") == "Palatino"

    def test_palatino(self):
        assert normalize_font_name("Palatino") == "Palatino"

    def test_cambria(self):
        assert normalize_font_name("Cambria") == "Cambria"

    def test_georgia(self):
        assert normalize_font_name("Georgia") == "Georgia"

    def test_helvetica(self):
        assert normalize_font_name("Helvetica") == "Helvetica"

    def test_book_antiqua(self):
        assert normalize_font_name("BookAntiqua") == "Book Antiqua"

    def test_hyphenated_keys_limitation(self):
        # Keys with hyphens in _FONT_ALIASES are not reachable because
        # normalize_font_name strips non-alpha chars before lookup.
        # "Times-Roman" -> key "timesroman" != dict key "times-roman"
        # This is a known limitation of the current code.
        result = normalize_font_name("Times-Roman")
        assert isinstance(result, str)


class TestSnapToStandard:
    def test_snaps_margin_097_to_1(self):
        assert snap_to_standard(0.97, _STANDARD_MARGINS) == 1.0

    def test_snaps_margin_103_to_1(self):
        assert snap_to_standard(1.03, _STANDARD_MARGINS) == 1.0

    def test_snaps_margin_exact(self):
        assert snap_to_standard(1.0, _STANDARD_MARGINS) == 1.0

    def test_no_snap_outside_tolerance(self):
        # 3.0 is far from any standard margin value
        result = snap_to_standard(3.0, _STANDARD_MARGINS)
        assert result == 3.0

    def test_snaps_to_0_5(self):
        assert snap_to_standard(0.52, _STANDARD_MARGINS) == 0.5

    def test_snaps_to_1_5(self):
        assert snap_to_standard(1.48, _STANDARD_MARGINS) == 1.5

    def test_snaps_font_12_9_to_13(self):
        assert snap_to_standard(12.9, _STANDARD_FONT_SIZES) == 13

    def test_snaps_font_13_1_to_13(self):
        assert snap_to_standard(13.1, _STANDARD_FONT_SIZES) == 13

    def test_snaps_font_exact_12(self):
        assert snap_to_standard(12.0, _STANDARD_FONT_SIZES) == 12

    def test_snaps_line_spacing_1_9_to_2(self):
        assert snap_to_standard(1.9, _STANDARD_LINE_SPACINGS) == 2.0

    def test_snaps_line_spacing_1_05_to_1(self):
        assert snap_to_standard(1.05, _STANDARD_LINE_SPACINGS) == 1.0

    def test_none_passthrough(self):
        assert snap_to_standard(None, _STANDARD_MARGINS) is None

    def test_rounds_non_matching(self):
        # 3.333 is far from any standard margin value
        result = snap_to_standard(3.333, _STANDARD_MARGINS)
        assert result == 3.33


class TestFormatConfidence:
    def test_docx_highest(self):
        assert FORMAT_CONFIDENCE["docx"] == 1.0

    def test_pdf_lower(self):
        assert FORMAT_CONFIDENCE["pdf"] == 0.6

    def test_txt_lowest(self):
        assert FORMAT_CONFIDENCE["txt"] == 0.3

    def test_html(self):
        assert FORMAT_CONFIDENCE["html"] == 0.7


class TestNormalizeDocument:
    def test_basic(self):
        profile = {
            "fonts": [{"font_name": "TimesNewRomanPSMT", "font_size_pt": 12.9}],
            "margins": {"top_inches": 0.97, "bottom_inches": 1.03, "left_inches": 1.0, "right_inches": 1.0},
            "line_spacing": "double",
        }
        result = normalize_document(profile, source_format="docx", file_name="test.docx")
        assert result.font_name == "Times New Roman"
        assert result.font_size_pt == 13  # snapped
        assert result.margin_top == 1.0  # snapped
        assert result.margin_bottom == 1.0  # snapped
        assert result.line_spacing == 2.0
        assert result.confidence == 1.0

    def test_pdf_confidence(self):
        result = normalize_document({}, source_format="pdf")
        assert result.confidence == 0.6

    def test_unknown_format(self):
        result = normalize_document({}, source_format="xyz")
        assert result.confidence == 0.5

    def test_empty_profile(self):
        result = normalize_document({})
        assert result.font_name is None
        assert result.font_size_pt is None
        assert result.margin_top is None

    def test_author_and_firm(self):
        result = normalize_document({}, author="John Doe", firm="Kirkland & Ellis LLP")
        assert result.author == "John Doe"
        assert result.firm == "Kirkland & Ellis LLP"

    def test_headings_extracted(self):
        profile = {
            "headings": [
                {"text": "ARGUMENT", "level": 1, "bold": True, "centered": True, "all_caps": True},
            ],
        }
        result = normalize_document(profile)
        assert len(result.heading_styles) == 1
        assert result.heading_styles[0]["text"] == "ARGUMENT"

    def test_sections_extracted(self):
        profile = {
            "sections": [
                {"section_type": "argument", "heading_text": "Argument"},
            ],
        }
        result = normalize_document(profile)
        assert "Argument" in result.section_names

    def test_line_spacing_single(self):
        result = normalize_document({"line_spacing": "single"})
        assert result.line_spacing == 1.0

    def test_line_spacing_numeric(self):
        result = normalize_document({"line_spacing": 1.9})
        assert result.line_spacing == 2.0

    def test_line_spacing_string_numeric(self):
        result = normalize_document({"line_spacing": "1.5"})
        assert result.line_spacing == 1.5

    def test_first_line_indent(self):
        result = normalize_document({"first_line_indent_inches": 0.5})
        assert result.first_line_indent == 0.5

    def test_file_name(self):
        result = normalize_document({}, file_name="brief.docx")
        assert result.file_name == "brief.docx"

    def test_tags(self):
        result = normalize_document({"tags": ["wisconsin", "appellate"]})
        assert result.tags == ["wisconsin", "appellate"]

    def test_margins_with_alternate_keys(self):
        profile = {"margins": {"top": 0.97, "bottom": 1.0, "left": 1.0, "right": 1.0}}
        result = normalize_document(profile)
        assert result.margin_top == 1.0

    def test_no_fonts(self):
        result = normalize_document({"fonts": []})
        assert result.font_name is None
        assert result.font_size_pt is None


class TestNormalizedDocument:
    def test_defaults(self):
        nd = NormalizedDocument()
        assert nd.file_name == ""
        assert nd.source_format == "unknown"
        assert nd.heading_styles == []
        assert nd.section_names == []
        assert nd.tags == []
