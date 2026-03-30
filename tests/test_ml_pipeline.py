"""Tests for the ML pipeline: normalizer, features, learner, synthesizer."""

import json
import tempfile
from pathlib import Path

import pytest

from legal_format_engine.ml.normalizer import (
    NormalizedDocument,
    NormalizedFont,
    NormalizedHeading,
    NormalizedMargins,
    NormalizedSection,
    canonicalize_font_name,
    normalize_brief_analysis,
    snap_font_size,
    snap_indent,
    snap_line_spacing,
    snap_margin,
)
from legal_format_engine.ml.features import (
    DocumentFeatures,
    extract_features,
)
from legal_format_engine.ml.learner import (
    FormatLearner,
    LearnedFormat,
    _percentile,
    _weighted_median,
)
from legal_format_engine.ml.synthesizer import (
    FormatRecommendation,
    diff_against_ruleset,
    synthesize_ruleset,
)
from legal_format_engine.ml.pipeline import MLPipeline
from legal_format_engine.models.patterns import (
    BriefAnalysis,
    FontPattern,
    HeadingPattern,
    MarginPattern,
    SectionPattern,
)


# ── Normalizer Tests ──────────────────────────────────────────────────


class TestFontCanonicalization:
    def test_times_new_roman_psmt(self):
        assert canonicalize_font_name("TimesNewRomanPSMT") == "Times New Roman"

    def test_times_new_roman_exact(self):
        assert canonicalize_font_name("Times New Roman") == "Times New Roman"

    def test_times_bold(self):
        assert canonicalize_font_name("Times-Bold") == "Times New Roman"

    def test_arial_mt(self):
        assert canonicalize_font_name("ArialMT") == "Arial"

    def test_helvetica(self):
        assert canonicalize_font_name("Helvetica") == "Arial"

    def test_courier_new_psmt(self):
        assert canonicalize_font_name("CourierNewPSMT") == "Courier New"

    def test_century_schoolbook(self):
        assert canonicalize_font_name("CenturySchoolbook") == "Century Schoolbook"

    def test_unknown_font_passthrough(self):
        assert canonicalize_font_name("SomeObscureFont") == "SomeObscureFont"

    def test_liberation_serif(self):
        assert canonicalize_font_name("LiberationSerif") == "Times New Roman"

    def test_garamond(self):
        assert canonicalize_font_name("Garamond") == "Garamond"


class TestMeasurementSnapping:
    def test_snap_margin_exact(self):
        assert snap_margin(1.0) == 1.0

    def test_snap_margin_close_to_one(self):
        assert snap_margin(0.97) == 1.0

    def test_snap_margin_close_to_1_25(self):
        assert snap_margin(1.22) == 1.25

    def test_snap_margin_close_to_2(self):
        assert snap_margin(1.95) == 2.0

    def test_snap_font_size_exact(self):
        assert snap_font_size(12.0) == 12.0

    def test_snap_font_size_close(self):
        assert snap_font_size(11.8) == 12.0

    def test_snap_font_size_10(self):
        assert snap_font_size(9.7) == 10.0

    def test_snap_line_spacing_double(self):
        assert snap_line_spacing(2.1) == 2.0

    def test_snap_line_spacing_single(self):
        assert snap_line_spacing(0.9) == 1.0

    def test_snap_indent_half(self):
        assert snap_indent(0.48) == 0.5


class TestNormalizeBriefAnalysis:
    def test_basic_normalization(self):
        analysis = BriefAnalysis(
            id="test1",
            source_filename="test.docx",
            analyzed_at="2024-01-01T00:00:00Z",
            font_patterns=[FontPattern(font_name="TimesNewRomanPSMT", font_size_pt=11.8)],
            margin_pattern=MarginPattern(top=0.97, bottom=1.03, left=1.48, right=1.52),
            line_spacing=2.1,
            heading_patterns=[
                HeadingPattern(level=1, case_style="upper", alignment="center", bold=True),
            ],
            section_patterns=[
                SectionPattern(id="argument", common_names=["ARGUMENT"], typical_order=5),
            ],
        )

        doc = normalize_brief_analysis(analysis, source_format="docx")

        assert doc.primary_font is not None
        assert doc.primary_font.family == "Times New Roman"
        assert doc.primary_font.size_pt == 12.0
        assert doc.margins is not None
        assert doc.margins.top == 1.0
        assert doc.margins.left == 1.5
        assert doc.margins.source_quality == "exact"
        assert doc.line_spacing == 2.0
        assert doc.extraction_confidence == 1.0

    def test_pdf_gets_lower_confidence(self):
        analysis = BriefAnalysis(
            id="test2",
            source_filename="test.pdf",
            analyzed_at="2024-01-01T00:00:00Z",
        )
        doc = normalize_brief_analysis(analysis, source_format="pdf")
        assert doc.extraction_confidence == 0.6

    def test_headings_preserved(self):
        analysis = BriefAnalysis(
            id="test3",
            source_filename="test.docx",
            analyzed_at="2024-01-01T00:00:00Z",
            heading_patterns=[
                HeadingPattern(level=1, case_style="title", alignment="center", bold=True),
                HeadingPattern(level=2, case_style="upper", alignment="left", bold=True,
                             numbering="roman"),
            ],
        )
        doc = normalize_brief_analysis(analysis, source_format="docx")
        assert len(doc.heading_styles) == 2
        assert doc.heading_styles[0].level == 1
        assert doc.heading_styles[1].numbering == "roman"


# ── Feature Extraction Tests ──────────────────────────────────────────


class TestFeatureExtraction:
    def _make_doc(self, **kwargs) -> NormalizedDocument:
        defaults = {
            "source_filename": "test.docx",
            "source_format": "docx",
            "extraction_confidence": 1.0,
        }
        defaults.update(kwargs)
        return NormalizedDocument(**defaults)

    def test_font_features(self):
        doc = self._make_doc(
            primary_font=NormalizedFont(family="Times New Roman", size_pt=12.0),
        )
        features = extract_features(doc)
        assert features.font_family is not None
        assert features.font_family.value == "Times New Roman"
        assert features.font_family.weight == 1.0

    def test_margin_features_docx(self):
        doc = self._make_doc(
            margins=NormalizedMargins(top=1.0, bottom=1.0, left=1.0, right=1.0),
        )
        features = extract_features(doc)
        assert features.margin_top is not None
        assert features.margin_top.value == 1.0
        assert features.margin_top.weight == 1.0

    def test_margin_features_pdf_lower_weight(self):
        doc = self._make_doc(
            extraction_confidence=0.6,
            margins=NormalizedMargins(
                top=1.0, bottom=1.0, left=1.0, right=1.0,
                source_quality="estimated",
            ),
        )
        features = extract_features(doc)
        assert features.margin_top is not None
        # PDF (0.6) * estimated (0.6) = 0.36
        assert features.margin_top.weight == pytest.approx(0.36, abs=0.01)

    def test_heading_features(self):
        doc = self._make_doc(
            heading_styles=[
                NormalizedHeading(level=1, case_style="title", alignment="center", bold=True),
            ],
        )
        features = extract_features(doc)
        assert 1 in features.heading_features
        hf = features.heading_features[1]
        assert hf.case_style.value == "title"
        assert hf.bold.value == 1.0

    def test_section_features(self):
        doc = self._make_doc(
            sections=[
                NormalizedSection(id="argument", original_name="Argument", order=0),
                NormalizedSection(id="conclusion", original_name="Conclusion", order=1),
            ],
        )
        features = extract_features(doc)
        assert features.section_ids == ["argument", "conclusion"]
        assert features.section_count == 2


# ── Learner Tests ─────────────────────────────────────────────────────


class TestStatisticalHelpers:
    def test_percentile_median(self):
        assert _percentile([1, 2, 3, 4, 5], 50) == 3.0

    def test_percentile_q1(self):
        assert _percentile([1, 2, 3, 4, 5], 25) == 2.0

    def test_percentile_single(self):
        assert _percentile([42], 50) == 42

    def test_weighted_median_simple(self):
        result = _weighted_median([(1.0, 1.0), (2.0, 1.0), (3.0, 1.0)])
        assert result == 2.0

    def test_weighted_median_heavy_weight(self):
        result = _weighted_median([(1.0, 10.0), (2.0, 1.0), (3.0, 1.0)])
        assert result == 1.0


class TestFormatLearner:
    def _make_features(self, font="Times New Roman", size=12.0,
                       margin=1.0, confidence=1.0) -> DocumentFeatures:
        doc = NormalizedDocument(
            source_filename="test.docx",
            source_format="docx",
            extraction_confidence=confidence,
            primary_font=NormalizedFont(family=font, size_pt=size),
            margins=NormalizedMargins(top=margin, bottom=margin, left=margin, right=margin),
            line_spacing=2.0,
            heading_styles=[
                NormalizedHeading(level=1, case_style="title", alignment="center", bold=True),
            ],
            sections=[
                NormalizedSection(id="argument", original_name="Argument", order=0),
            ],
        )
        return extract_features(doc)

    def test_learns_from_single_doc(self):
        learner = FormatLearner()
        learner.add(self._make_features())
        result = learner.learn()

        assert result.document_count == 1
        assert result.font_family is not None
        assert result.font_family.value == "Times New Roman"

    def test_learns_consensus_from_multiple(self):
        learner = FormatLearner()
        for _ in range(5):
            learner.add(self._make_features(font="Times New Roman", size=12.0))
        learner.add(self._make_features(font="Arial", size=14.0))  # outlier

        result = learner.learn()
        assert result.font_family.value == "Times New Roman"
        assert result.font_size_pt.value == 12.0
        assert result.font_family.agreement > 0.7

    def test_outlier_rejection_on_margins(self):
        learner = FormatLearner()
        # 5 docs with 1" margins
        for _ in range(5):
            learner.add(self._make_features(margin=1.0))
        # 1 outlier with 3" margins
        learner.add(self._make_features(margin=3.0))

        result = learner.learn()
        assert result.margin_top.value == 1.0

    def test_pdf_lower_weight_than_docx(self):
        learner = FormatLearner()
        # 2 DOCX with Times New Roman
        learner.add(self._make_features(font="Times New Roman", confidence=1.0))
        learner.add(self._make_features(font="Times New Roman", confidence=1.0))
        # 3 PDFs with Arial (lower confidence)
        for _ in range(3):
            learner.add(self._make_features(font="Arial", confidence=0.6))

        result = learner.learn()
        # Despite more Arial docs, Times should win due to higher weight
        assert result.font_family.value == "Times New Roman"

    def test_learns_headings(self):
        learner = FormatLearner()
        for _ in range(3):
            learner.add(self._make_features())
        result = learner.learn()

        assert len(result.heading_styles) > 0
        assert result.heading_styles[0].level == 1

    def test_learns_sections(self):
        learner = FormatLearner()
        for _ in range(3):
            learner.add(self._make_features())
        result = learner.learn()

        assert len(result.section_order) > 0
        assert result.section_order[0].id == "argument"

    def test_empty_learner_returns_empty(self):
        learner = FormatLearner()
        result = learner.learn()
        assert result.document_count == 0
        assert result.overall_confidence == 0.0


# ── Synthesizer Tests ─────────────────────────────────────────────────


class TestSynthesizer:
    def _make_learned(self) -> LearnedFormat:
        learner = FormatLearner()
        for _ in range(5):
            doc = NormalizedDocument(
                source_filename="test.docx",
                source_format="docx",
                extraction_confidence=1.0,
                primary_font=NormalizedFont(family="Times New Roman", size_pt=12.0),
                margins=NormalizedMargins(top=1.0, bottom=1.0, left=1.5, right=1.5),
                line_spacing=2.0,
                heading_styles=[
                    NormalizedHeading(level=1, case_style="title", alignment="center", bold=True),
                    NormalizedHeading(level=2, case_style="upper", alignment="left", bold=True,
                                    numbering="roman"),
                ],
                sections=[
                    NormalizedSection(id="table_of_contents", original_name="Table of Contents", order=0),
                    NormalizedSection(id="argument", original_name="Argument", order=1),
                    NormalizedSection(id="conclusion", original_name="Conclusion", order=2),
                ],
            )
            learner.add(extract_features(doc))
        return learner.learn()

    def test_synthesize_produces_valid_ruleset(self):
        learned = self._make_learned()
        ruleset = synthesize_ruleset(learned, "wisconsin", "appellate", "brief")

        assert ruleset["jurisdiction"] == "wisconsin"
        assert ruleset["court_level"] == "appellate"
        assert ruleset["document_type"] == "brief"
        assert "page_format" in ruleset

    def test_synthesize_captures_font(self):
        learned = self._make_learned()
        ruleset = synthesize_ruleset(learned)

        pf = ruleset.get("page_format", {})
        assert pf.get("font_name") == "Times New Roman"
        assert pf.get("font_size_pt") == 12.0

    def test_synthesize_captures_margins(self):
        learned = self._make_learned()
        ruleset = synthesize_ruleset(learned)

        pf = ruleset.get("page_format", {})
        assert pf.get("margin_top_inches") == 1.0
        assert pf.get("margin_left_inches") == 1.5

    def test_synthesize_captures_headings(self):
        learned = self._make_learned()
        ruleset = synthesize_ruleset(learned)

        assert "heading_rules" in ruleset
        assert len(ruleset["heading_rules"]) >= 2

    def test_synthesize_captures_sections(self):
        learned = self._make_learned()
        ruleset = synthesize_ruleset(learned)

        assert "required_sections" in ruleset
        section_ids = [s["id"] for s in ruleset["required_sections"]]
        assert "argument" in section_ids

    def test_diff_detects_font_change(self):
        learned = self._make_learned()
        existing = {
            "page_format": {
                "font_name": "Arial",
                "font_size_pt": 14.0,
            },
        }
        recs = diff_against_ruleset(learned, existing)
        fields = [r.field for r in recs]
        assert "page_format.font_name" in fields

    def test_diff_no_recommendations_when_matching(self):
        learned = self._make_learned()
        existing = {
            "page_format": {
                "font_name": "Times New Roman",
                "font_size_pt": 12.0,
                "line_spacing": 2.0,
                "margin_top_inches": 1.0,
                "margin_bottom_inches": 1.0,
                "margin_left_inches": 1.5,
                "margin_right_inches": 1.5,
            },
        }
        recs = diff_against_ruleset(learned, existing)
        assert len(recs) == 0


# ── Pipeline Integration Tests ────────────────────────────────────────


class TestMLPipeline:
    def test_pipeline_stats_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = MLPipeline(store_dir=Path(tmpdir))
            stats = pipeline.get_stats()
            assert stats["total_documents"] == 0

    def test_pipeline_learn_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = MLPipeline(store_dir=Path(tmpdir))
            learned = pipeline.learn(jurisdiction="wisconsin")
            assert learned.document_count == 0

    def test_pipeline_list_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = MLPipeline(store_dir=Path(tmpdir))
            docs = pipeline.list_documents()
            assert docs == []

    def test_pipeline_delete_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = MLPipeline(store_dir=Path(tmpdir))
            assert pipeline.delete_document("nonexistent") is False

    def test_pipeline_suggest_ruleset_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = MLPipeline(store_dir=Path(tmpdir))
            ruleset = pipeline.suggest_ruleset(jurisdiction="wisconsin")
            assert ruleset["jurisdiction"] == "wisconsin"
            assert ruleset["_ml_metadata"]["document_count"] == 0
