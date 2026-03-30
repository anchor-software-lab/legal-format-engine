"""Tests for the features module."""

import pytest
from anchor_ml_engine.features import extract_features
from anchor_ml_engine.models import (
    NormalizedDocument,
    NormalizedFont,
    NormalizedHeading,
    NormalizedMargins,
    NormalizedSection,
)


class TestExtractFeatures:
    def test_basic_extraction(self, sample_normalized_doc):
        features = extract_features(sample_normalized_doc)
        assert features.document_id == "test001"
        assert features.font_family is not None
        assert features.font_family.value == "Times New Roman"
        assert features.font_size_pt.value == 12.0
        assert features.line_spacing.value == 2.0

    def test_margin_features(self, sample_normalized_doc):
        features = extract_features(sample_normalized_doc)
        assert features.margin_top is not None
        assert features.margin_top.value == 1.0
        assert features.margin_left.value == 1.0

    def test_margin_weight_reduced_for_pdf(self):
        doc = NormalizedDocument(
            source_filename="test.pdf",
            source_format="pdf",
            extraction_confidence=0.6,
            margins=NormalizedMargins(top=1.0, bottom=1.0, left=1.0, right=1.0,
                                     source_quality="estimated"),
        )
        features = extract_features(doc)
        # Base weight is 0.6 (PDF), margin weight is 0.6 * 0.6 = 0.36
        assert features.margin_top.weight == pytest.approx(0.36)

    def test_heading_features(self, sample_normalized_doc):
        features = extract_features(sample_normalized_doc)
        assert 1 in features.heading_features
        assert 2 in features.heading_features
        h1 = features.heading_features[1]
        assert h1.case_style.value == "upper"
        assert h1.alignment.value == "center"
        assert h1.bold.value == 1.0

    def test_heading_weight_reduced_for_few_samples(self):
        doc = NormalizedDocument(
            source_filename="test.docx",
            source_format="docx",
            extraction_confidence=1.0,
            heading_styles=[
                NormalizedHeading(level=1, case_style="upper", alignment="center",
                                 bold=True, sample_count=2),
            ],
        )
        features = extract_features(doc)
        h1 = features.heading_features[1]
        assert h1.case_style.weight == 0.5  # reduced for sample_count < 3

    def test_section_features(self, sample_normalized_doc):
        features = extract_features(sample_normalized_doc)
        assert features.section_ids == ["table_of_contents", "argument", "conclusion"]
        assert features.section_count == 3

    def test_indentation_features(self, sample_normalized_doc):
        features = extract_features(sample_normalized_doc)
        assert features.body_indent is not None
        assert features.body_indent.value == 0.5
        assert features.block_quote_indent.value == 0.5

    def test_empty_document(self):
        doc = NormalizedDocument(
            source_filename="empty.docx",
            source_format="docx",
        )
        features = extract_features(doc)
        assert features.font_family is None
        assert features.margin_top is None
        assert features.heading_features == {}
