"""Tests for the TensorFlow data pipeline: feature conversion, encoding, masking, datasets."""

from __future__ import annotations

import numpy as np
import pytest
import tensorflow as tf

from anchor_ml_engine.tf.data_pipeline import (
    COURT_LEVELS,
    DOCUMENT_TYPES,
    FONT_FAMILIES,
    MISSING_VALUE,
    NUM_FONT_FAMILIES,
    NUM_FORMAT_FEATURES,
    NUM_JURISDICTIONS,
    NUM_NUMERICAL_FEATURES,
    build_classifier_dataset,
    build_heading_dataset,
    build_predictor_dataset,
    build_training_dataset,
    encode_categorical,
    encode_font_family,
    encode_jurisdiction,
    features_to_font_onehot,
    features_to_mask,
    features_to_numerical,
    features_to_tensor,
)
from anchor_ml_engine.models import (
    DocumentFeatures,
    FeatureValue,
    NormalizedFont,
    NormalizedMargins,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_doc_features(
    font_family: str = "Times New Roman",
    font_size: float = 12.0,
    margin_top: float = 1.0,
    margin_bottom: float = 1.0,
    margin_left: float = 1.0,
    margin_right: float = 1.0,
    line_spacing: float = 2.0,
    body_indent: float = 0.5,
    block_quote_indent: float = 1.0,
    section_count: int = 5,
) -> DocumentFeatures:
    """Create a DocumentFeatures with known values for testing."""
    fv = lambda name, value: FeatureValue(name=name, value=value, weight=1.0, source="test")
    return DocumentFeatures(
        document_id="test-001",
        source_filename="test.docx",
        font_family=fv("font_family", font_family),
        font_size_pt=fv("font_size_pt", font_size),
        margin_top=fv("margin_top", margin_top),
        margin_bottom=fv("margin_bottom", margin_bottom),
        margin_left=fv("margin_left", margin_left),
        margin_right=fv("margin_right", margin_right),
        line_spacing=fv("line_spacing", line_spacing),
        body_indent=fv("body_indent", body_indent),
        block_quote_indent=fv("block_quote_indent", block_quote_indent),
        section_count=section_count,
    )


def _make_partial_features() -> DocumentFeatures:
    """Create a DocumentFeatures with some missing values."""
    fv = lambda name, value: FeatureValue(name=name, value=value, weight=1.0, source="test")
    return DocumentFeatures(
        document_id="test-partial",
        source_filename="partial.docx",
        font_size_pt=fv("font_size_pt", 12.0),
        margin_left=fv("margin_left", 1.0),
        # Everything else is None/missing
        section_count=3,
    )


@pytest.fixture
def doc_features():
    return _make_doc_features()


@pytest.fixture
def partial_features():
    return _make_partial_features()


@pytest.fixture
def feature_list():
    """A small list of features for dataset building."""
    return [
        _make_doc_features(font_size=12.0, margin_top=1.0),
        _make_doc_features(font_family="Arial", font_size=11.0, margin_top=1.5),
        _make_doc_features(font_family="Courier New", font_size=10.0, margin_top=0.75),
        _make_doc_features(font_family="Calibri", font_size=12.0, margin_top=1.25),
        _make_doc_features(font_family="Georgia", font_size=13.0, margin_top=1.0),
    ]


# ---------------------------------------------------------------------------
# Test categorical encoding
# ---------------------------------------------------------------------------


class TestCategoricalEncoding:
    def test_encode_font_family_known(self):
        vec = encode_font_family("Times New Roman")
        assert vec.shape == (NUM_FONT_FAMILIES,)
        assert vec.sum() == 1.0
        assert vec[0] == 1.0  # Times New Roman is first

    def test_encode_font_family_other(self):
        vec = encode_font_family("Comic Sans MS")
        assert vec.shape == (NUM_FONT_FAMILIES,)
        assert vec[-1] == 1.0  # maps to "Other"

    def test_encode_font_family_none(self):
        vec = encode_font_family(None)
        assert vec.shape == (NUM_FONT_FAMILIES,)
        assert vec.sum() == 0.0

    def test_encode_jurisdiction(self):
        jlist = ["WI", "IL", "MN", "CA"]
        vec = encode_jurisdiction("IL", jlist)
        assert vec.shape == (NUM_JURISDICTIONS,)
        assert vec[1] == 1.0

    def test_encode_jurisdiction_unknown(self):
        jlist = ["WI", "IL"]
        vec = encode_jurisdiction("ZZ", jlist)
        assert vec.sum() == 0.0

    def test_encode_jurisdiction_none(self):
        vec = encode_jurisdiction(None)
        assert vec.sum() == 0.0

    def test_encode_categorical_generic(self):
        categories = ["a", "b", "c"]
        vec = encode_categorical("b", categories)
        assert vec.shape == (3,)
        assert vec[1] == 1.0

    def test_encode_categorical_unknown(self):
        vec = encode_categorical("z", ["a", "b"])
        assert vec.sum() == 0.0


# ---------------------------------------------------------------------------
# Test feature conversion to tensors
# ---------------------------------------------------------------------------


class TestFeatureConversion:
    def test_features_to_numerical_shape(self, doc_features):
        arr = features_to_numerical(doc_features)
        assert arr.shape == (NUM_NUMERICAL_FEATURES,)
        assert arr.dtype == np.float32

    def test_features_to_numerical_values(self, doc_features):
        arr = features_to_numerical(doc_features)
        assert arr[0] == 12.0  # font_size
        assert arr[1] == 1.0   # margin_top
        assert arr[5] == 2.0   # line_spacing

    def test_features_to_font_onehot(self, doc_features):
        arr = features_to_font_onehot(doc_features)
        assert arr.shape == (NUM_FONT_FAMILIES,)
        assert arr[0] == 1.0  # Times New Roman

    def test_features_to_tensor_shape(self, doc_features):
        arr = features_to_tensor(doc_features)
        assert arr.shape == (NUM_FORMAT_FEATURES,)
        assert arr.dtype == np.float32

    def test_features_to_tensor_combined(self, doc_features):
        arr = features_to_tensor(doc_features)
        # First NUM_NUMERICAL_FEATURES are numerical, rest are font one-hot
        assert arr[0] == 12.0  # font_size
        assert arr[NUM_NUMERICAL_FEATURES] == 1.0  # first font slot

    def test_partial_features_numerical(self, partial_features):
        arr = features_to_numerical(partial_features)
        assert arr[0] == 12.0  # font_size is present
        assert arr[3] == 1.0   # margin_left is present
        assert arr[1] == MISSING_VALUE  # margin_top is missing
        assert arr[5] == MISSING_VALUE  # line_spacing is missing


# ---------------------------------------------------------------------------
# Test masking
# ---------------------------------------------------------------------------


class TestMasking:
    def test_full_mask(self, doc_features):
        mask = features_to_mask(doc_features)
        assert mask.shape == (NUM_FORMAT_FEATURES,)
        # All features present
        assert mask.sum() == NUM_FORMAT_FEATURES

    def test_partial_mask(self, partial_features):
        mask = features_to_mask(partial_features)
        assert mask.shape == (NUM_FORMAT_FEATURES,)
        # Only font_size, margin_left, section_count are present (no font family)
        # So numerical mask has 1s for font_size(0), margin_left(3), section_count(8)
        assert mask[0] == 1.0  # font_size
        assert mask[3] == 1.0  # margin_left
        assert mask[8] == 1.0  # section_count
        assert mask[1] == 0.0  # margin_top missing
        assert mask[5] == 0.0  # line_spacing missing
        # Font: no font family => all font slots are 0
        for i in range(NUM_NUMERICAL_FEATURES, NUM_FORMAT_FEATURES):
            assert mask[i] == 0.0


# ---------------------------------------------------------------------------
# Test dataset builders
# ---------------------------------------------------------------------------


class TestDatasetBuilders:
    def test_build_training_dataset(self, feature_list):
        ds = build_training_dataset(feature_list, batch_size=2, shuffle=False)
        batch = next(iter(ds))
        assert batch.shape[0] == 2  # batch_size
        assert batch.shape[1] == NUM_FORMAT_FEATURES

    def test_build_training_dataset_all_batches(self, feature_list):
        ds = build_training_dataset(feature_list, batch_size=2, shuffle=False)
        total = 0
        for batch in ds:
            total += batch.shape[0]
        assert total == len(feature_list)

    def test_build_classifier_dataset(self, feature_list):
        n = len(feature_list)
        ds = build_classifier_dataset(
            feature_list,
            jurisdiction_labels=[0, 1, 2, 3, 4],
            court_level_labels=[0, 1, 2, 0, 1],
            doc_type_labels=[0, 0, 1, 2, 3],
            batch_size=2,
            shuffle=False,
        )
        inputs, outputs = next(iter(ds))
        assert inputs["numerical_input"].shape == (2, NUM_NUMERICAL_FEATURES)
        assert inputs["font_input"].shape == (2, NUM_FONT_FAMILIES)
        assert outputs["jurisdiction"].shape == (2, NUM_JURISDICTIONS)
        assert outputs["court_level"].shape == (2, len(COURT_LEVELS))
        assert outputs["document_type"].shape == (2, len(DOCUMENT_TYPES))

    def test_build_heading_dataset(self):
        n = 10
        text_feat = np.random.rand(n, 5).astype(np.float32)
        fmt_feat = np.random.rand(n, 4).astype(np.float32)
        labels = np.random.randint(0, 5, n).astype(np.int32)

        ds = build_heading_dataset(text_feat, fmt_feat, labels, batch_size=4, shuffle=False)
        features_batch, labels_batch = next(iter(ds))
        assert features_batch.shape == (4, 9)  # 5 text + 4 format
        assert labels_batch.shape == (4, 5)    # one-hot

    def test_build_predictor_dataset(self, feature_list):
        n = len(feature_list)
        jurisdictions = np.zeros((n, NUM_JURISDICTIONS), dtype=np.float32)
        for i in range(n):
            jurisdictions[i, i % NUM_JURISDICTIONS] = 1.0

        ds = build_predictor_dataset(
            feature_list,
            jurisdictions,
            mask_ratio=0.3,
            batch_size=2,
            shuffle=False,
        )
        inputs, targets = next(iter(ds))
        assert inputs["format_input"].shape == (2, NUM_FORMAT_FEATURES)
        assert inputs["mask_input"].shape == (2, NUM_FORMAT_FEATURES)
        assert inputs["jurisdiction_input"].shape == (2, NUM_JURISDICTIONS)
        assert targets.shape == (2, NUM_FORMAT_FEATURES)
