"""Tests for ml/learner.py."""

from __future__ import annotations

import pytest

from legal_format_engine.ml.learner import (
    LearnedPatterns,
    _weighted_median,
    learn_patterns,
)
from legal_format_engine.ml.features import FeatureVector


class TestWeightedMedian:
    def test_single_value(self):
        val, conf = _weighted_median([(13.0, 1.0)])
        assert val == 13.0
        assert conf > 0

    def test_two_values(self):
        val, conf = _weighted_median([(12.0, 1.0), (14.0, 1.0)])
        assert val is not None
        assert 12.0 <= val <= 14.0

    def test_weighted_towards_heavier(self):
        val, conf = _weighted_median([(12.0, 0.1), (13.0, 10.0)])
        assert val == 13.0

    def test_empty(self):
        val, conf = _weighted_median([])
        assert val is None
        assert conf == 0.0

    def test_outlier_rejection_iqr(self):
        """IQR should reject extreme outliers."""
        values = [(1.0, 1.0)] * 10 + [(100.0, 1.0)]  # 100 is an outlier
        val, conf = _weighted_median(values)
        assert val == 1.0

    def test_all_same(self):
        val, conf = _weighted_median([(13.0, 1.0)] * 5)
        assert val == 13.0

    def test_zero_weights(self):
        val, conf = _weighted_median([(13.0, 0.0)])
        assert val is None

    def test_three_values_median(self):
        val, conf = _weighted_median([(10.0, 1.0), (12.0, 1.0), (14.0, 1.0)])
        assert val is not None
        assert 10.0 <= val <= 14.0

    def test_confidence_proportion(self):
        val, conf = _weighted_median([(13.0, 1.0), (13.0, 1.0)])
        assert conf > 0
        assert conf <= 1.0


class TestLearnPatterns:
    def test_empty(self):
        result = learn_patterns([])
        assert result.document_count == 0
        assert result.font_name is None

    def test_single_document(self):
        fv = FeatureVector(
            font_name=("Times New Roman", 1.0),
            font_size=(13.0, 1.0),
            margin_top=(1.0, 1.0),
            margin_bottom=(1.0, 1.0),
            margin_left=(1.0, 1.0),
            margin_right=(1.0, 1.0),
            line_spacing=(2.0, 1.0),
            first_line_indent=(0.5, 1.0),
            jurisdiction="wisconsin",
        )
        result = learn_patterns([fv])
        assert result.document_count == 1
        assert result.font_name == "Times New Roman"
        assert result.font_size_pt == 13.0
        assert result.margin_top == 1.0
        assert result.line_spacing == 2.0
        assert result.first_line_indent == 0.5
        assert result.jurisdiction == "wisconsin"

    def test_font_voting(self):
        vectors = [
            FeatureVector(font_name=("Times New Roman", 1.0)),
            FeatureVector(font_name=("Times New Roman", 1.0)),
            FeatureVector(font_name=("Arial", 1.0)),
        ]
        result = learn_patterns(vectors)
        assert result.font_name == "Times New Roman"
        assert result.font_name_confidence > 0.5

    def test_font_voting_weighted(self):
        vectors = [
            FeatureVector(font_name=("Arial", 0.1)),
            FeatureVector(font_name=("Times New Roman", 10.0)),
        ]
        result = learn_patterns(vectors)
        assert result.font_name == "Times New Roman"

    def test_margin_confidence(self):
        vectors = [
            FeatureVector(
                margin_top=(1.0, 1.0),
                margin_bottom=(1.0, 1.0),
                margin_left=(1.0, 1.0),
                margin_right=(1.0, 1.0),
            ),
        ]
        result = learn_patterns(vectors)
        assert result.margin_confidence > 0

    def test_multiple_documents_consensus(self):
        vectors = [
            FeatureVector(font_size=(13.0, 1.0), margin_top=(1.0, 1.0)),
            FeatureVector(font_size=(13.0, 1.0), margin_top=(1.0, 1.0)),
            FeatureVector(font_size=(13.0, 1.0), margin_top=(1.0, 1.0)),
            FeatureVector(font_size=(12.0, 0.5)),  # outlier with low weight
        ]
        result = learn_patterns(vectors)
        assert result.font_size_pt == 13.0

    def test_no_font_data(self):
        vectors = [FeatureVector(), FeatureVector()]
        result = learn_patterns(vectors)
        assert result.font_name is None
        assert result.font_name_confidence == 0

    def test_document_count(self):
        vectors = [FeatureVector() for _ in range(7)]
        result = learn_patterns(vectors)
        assert result.document_count == 7


class TestLearnedPatterns:
    def test_defaults(self):
        lp = LearnedPatterns()
        assert lp.font_name is None
        assert lp.document_count == 0
        assert lp.margin_confidence == 0.0
