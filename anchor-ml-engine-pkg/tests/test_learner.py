"""Tests for the learner module."""

import pytest
from anchor_ml_engine.learner import (
    FormatLearner,
    _percentile,
    _weighted_median,
)
from anchor_ml_engine.features import extract_features
from anchor_ml_engine.models import (
    DocumentFeatures,
    FeatureValue,
    HeadingFeatures,
    NormalizedDocument,
    NormalizedFont,
    NormalizedHeading,
    NormalizedMargins,
)


class TestWeightedMedian:
    def test_single_value(self):
        assert _weighted_median([(5.0, 1.0)]) == 5.0

    def test_equal_weights(self):
        result = _weighted_median([(1.0, 1.0), (2.0, 1.0), (3.0, 1.0)])
        assert result == 2.0

    def test_weighted_towards_higher(self):
        result = _weighted_median([(1.0, 1.0), (3.0, 10.0)])
        assert result == 3.0

    def test_empty(self):
        assert _weighted_median([]) == 0.0


class TestPercentile:
    def test_median_odd(self):
        assert _percentile([1, 2, 3, 4, 5], 50) == 3.0

    def test_q1(self):
        result = _percentile([1, 2, 3, 4, 5, 6, 7, 8], 25)
        assert result == pytest.approx(2.75, abs=0.01)

    def test_q3(self):
        result = _percentile([1, 2, 3, 4, 5, 6, 7, 8], 75)
        assert result == pytest.approx(6.25, abs=0.01)

    def test_single_value(self):
        assert _percentile([42.0], 50) == 42.0

    def test_empty(self):
        assert _percentile([], 50) == 0.0


class TestFormatLearner:
    def test_learn_empty(self):
        learner = FormatLearner()
        result = learner.learn()
        assert result.document_count == 0
        assert result.overall_confidence == 0.0

    def test_learn_single_document(self, sample_features):
        learner = FormatLearner()
        learner.add(sample_features)
        result = learner.learn()
        assert result.document_count == 1
        assert result.font_family is not None
        assert result.font_family.value == "Times New Roman"

    def test_learn_multiple_documents(self, multiple_features):
        learner = FormatLearner()
        learner.add_all(multiple_features)
        result = learner.learn()
        assert result.document_count == 5
        assert result.font_family.value == "Times New Roman"
        assert result.font_size_pt.value == 12.0
        assert result.line_spacing.value == 2.0

    def test_count_property(self):
        learner = FormatLearner()
        assert learner.count == 0
        doc = NormalizedDocument(
            source_filename="test.docx", source_format="docx",
            primary_font=NormalizedFont(family="Arial", size_pt=12.0),
        )
        learner.add(extract_features(doc))
        assert learner.count == 1

    def test_categorical_voting(self):
        """Test that weighted voting picks the majority font."""
        learner = FormatLearner()
        for i in range(3):
            doc = NormalizedDocument(
                id=f"tnr_{i}",
                source_filename=f"tnr_{i}.docx",
                source_format="docx",
                primary_font=NormalizedFont(family="Times New Roman", size_pt=12.0),
            )
            learner.add(extract_features(doc))
        # Add 1 with Arial
        doc = NormalizedDocument(
            id="arial_0",
            source_filename="arial_0.docx",
            source_format="docx",
            primary_font=NormalizedFont(family="Arial", size_pt=12.0),
        )
        learner.add(extract_features(doc))

        result = learner.learn()
        assert result.font_family.value == "Times New Roman"
        assert result.font_family.agreement > 0.5

    def test_iqr_outlier_rejection(self):
        """Test that extreme outliers are rejected."""
        learner = FormatLearner()
        # 4 normal documents with 12pt font
        for i in range(4):
            doc = NormalizedDocument(
                id=f"normal_{i}",
                source_filename=f"normal_{i}.docx",
                source_format="docx",
                primary_font=NormalizedFont(family="Times New Roman", size_pt=12.0),
                margins=NormalizedMargins(top=1.0, bottom=1.0, left=1.0, right=1.0),
            )
            learner.add(extract_features(doc))
        # 1 outlier with 8pt font and 3" margins
        doc = NormalizedDocument(
            id="outlier",
            source_filename="outlier.docx",
            source_format="docx",
            primary_font=NormalizedFont(family="Times New Roman", size_pt=8.0),
            margins=NormalizedMargins(top=3.0, bottom=3.0, left=3.0, right=3.0),
        )
        learner.add(extract_features(doc))

        result = learner.learn()
        # Font size should be 12 (outlier rejected)
        assert result.font_size_pt.value == 12.0
        # Margins should be 1.0 (outlier rejected)
        assert result.margin_top.value == 1.0

    def test_learn_headings(self):
        learner = FormatLearner()
        for i in range(3):
            doc = NormalizedDocument(
                id=f"h_{i}",
                source_filename=f"h_{i}.docx",
                source_format="docx",
                heading_styles=[
                    NormalizedHeading(level=1, case_style="upper", alignment="center", bold=True),
                ],
            )
            learner.add(extract_features(doc))

        result = learner.learn()
        assert len(result.heading_styles) == 1
        assert result.heading_styles[0].level == 1
        assert result.heading_styles[0].case_style.value == "upper"

    def test_learn_sections(self):
        learner = FormatLearner()
        from anchor_ml_engine.models import NormalizedSection
        for i in range(3):
            doc = NormalizedDocument(
                id=f"s_{i}",
                source_filename=f"s_{i}.docx",
                source_format="docx",
                sections=[
                    NormalizedSection(id="argument", original_name="ARGUMENT", order=0),
                    NormalizedSection(id="conclusion", original_name="CONCLUSION", order=1),
                ],
            )
            learner.add(extract_features(doc))

        result = learner.learn()
        assert len(result.section_order) == 2
        assert result.section_order[0].id == "argument"
        assert result.section_order[0].frequency == 1.0

    def test_overall_confidence_increases_with_docs(self):
        learner = FormatLearner()
        doc = NormalizedDocument(
            source_filename="test.docx",
            source_format="docx",
            primary_font=NormalizedFont(family="Times New Roman", size_pt=12.0),
            margins=NormalizedMargins(top=1.0, bottom=1.0, left=1.0, right=1.0),
            line_spacing=2.0,
        )

        learner.add(extract_features(doc))
        result1 = learner.learn()

        # Add more identical documents
        for _ in range(9):
            learner.add(extract_features(doc))
        result10 = learner.learn()

        # More documents should increase confidence
        assert result10.overall_confidence >= result1.overall_confidence
