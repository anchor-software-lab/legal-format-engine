"""Data pipeline: convert domain models to TensorFlow datasets.

Converts NormalizedDocuments and DocumentFeatures into tf.data.Dataset
objects suitable for training the TF models.
"""

from __future__ import annotations

from typing import Any

try:
    import numpy as np
    import tensorflow as tf
except ImportError:
    raise ImportError(
        "TensorFlow is required for legal_format_engine.ml.tf.data_pipeline. "
        "Install with: pip install anchor-ml-engine[tf]"
    )

from legal_format_engine.ml.tf.models import (
    NUM_FONT_FAMILIES,
    NUM_FORMAT_FEATURES,
    NUM_JURISDICTIONS,
    NUM_NUMERICAL_FEATURES,
)

# ---------------------------------------------------------------------------
# Categorical encoding maps
# ---------------------------------------------------------------------------

FONT_FAMILIES = [
    "Times New Roman",
    "Arial",
    "Courier New",
    "Calibri",
    "Cambria",
    "Georgia",
    "Garamond",
    "Century Schoolbook",
    "Palatino",
    "Bookman Old Style",
    "Helvetica",
    "Other",
]
_FONT_TO_IDX = {f: i for i, f in enumerate(FONT_FAMILIES)}

# Use a fixed list; real deployment would load from jurisdiction registry.
# Index 0-63 maps to jurisdictions alphabetically or by ID.
JURISDICTION_LIST: list[str] = []  # populated at runtime or from config

COURT_LEVELS = ["trial", "appellate", "supreme"]
DOCUMENT_TYPES = ["brief", "motion", "memo", "order", "opinion"]

MISSING_VALUE = 0.0  # sentinel for missing numerical features


# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------

def encode_font_family(family: str | None) -> np.ndarray:
    """One-hot encode a font family name.

    Returns array of shape (NUM_FONT_FAMILIES,).
    Unknown fonts map to the 'Other' slot.
    """
    vec = np.zeros(NUM_FONT_FAMILIES, dtype=np.float32)
    if family is None:
        return vec
    idx = _FONT_TO_IDX.get(family, _FONT_TO_IDX["Other"])
    vec[idx] = 1.0
    return vec


def encode_jurisdiction(jurisdiction: str | None,
                        jurisdiction_list: list[str] | None = None) -> np.ndarray:
    """One-hot encode a jurisdiction.

    Returns array of shape (NUM_JURISDICTIONS,).
    """
    jlist = jurisdiction_list or JURISDICTION_LIST
    vec = np.zeros(NUM_JURISDICTIONS, dtype=np.float32)
    if jurisdiction is None or not jlist:
        return vec
    try:
        idx = jlist.index(jurisdiction)
        if idx < NUM_JURISDICTIONS:
            vec[idx] = 1.0
    except ValueError:
        pass
    return vec


def encode_categorical(value: str | None, categories: list[str]) -> np.ndarray:
    """Generic one-hot encoding for a categorical value.

    Returns array of shape (len(categories),).
    """
    vec = np.zeros(len(categories), dtype=np.float32)
    if value is None:
        return vec
    try:
        idx = categories.index(value)
        vec[idx] = 1.0
    except ValueError:
        pass
    return vec


# ---------------------------------------------------------------------------
# Feature conversion
# ---------------------------------------------------------------------------

def _get_numerical_value(feature_value: Any) -> float:
    """Extract numerical value from a FeatureValue or return MISSING_VALUE."""
    if feature_value is None:
        return MISSING_VALUE
    val = feature_value.value if hasattr(feature_value, "value") else feature_value
    if isinstance(val, (int, float)):
        return float(val)
    return MISSING_VALUE


def features_to_numerical(doc_features: Any) -> np.ndarray:
    """Convert a DocumentFeatures to a numerical feature array.

    Returns array of shape (NUM_NUMERICAL_FEATURES,).
    Order: font_size, margin_top, margin_bottom, margin_left, margin_right,
           line_spacing, body_indent, block_quote_indent, section_count
    """
    return np.array([
        _get_numerical_value(doc_features.font_size_pt),
        _get_numerical_value(doc_features.margin_top),
        _get_numerical_value(doc_features.margin_bottom),
        _get_numerical_value(doc_features.margin_left),
        _get_numerical_value(doc_features.margin_right),
        _get_numerical_value(doc_features.line_spacing),
        _get_numerical_value(doc_features.body_indent),
        _get_numerical_value(doc_features.block_quote_indent),
        float(doc_features.section_count),
    ], dtype=np.float32)


def features_to_font_onehot(doc_features: Any) -> np.ndarray:
    """Extract font family one-hot from DocumentFeatures.

    Returns array of shape (NUM_FONT_FAMILIES,).
    """
    family = None
    if doc_features.font_family is not None:
        val = doc_features.font_family.value
        if isinstance(val, str):
            family = val
    return encode_font_family(family)


def features_to_tensor(doc_features: Any) -> np.ndarray:
    """Convert a DocumentFeatures to a full format feature vector.

    Returns array of shape (NUM_FORMAT_FEATURES,) =
        numerical features + font one-hot encoding.
    """
    numerical = features_to_numerical(doc_features)
    font_oh = features_to_font_onehot(doc_features)
    return np.concatenate([numerical, font_oh])


def features_to_mask(doc_features: Any) -> np.ndarray:
    """Build a mask vector indicating which features are present.

    Returns array of shape (NUM_FORMAT_FEATURES,) with 1.0 for present, 0.0 for missing.
    """
    numerical_fields = [
        doc_features.font_size_pt,
        doc_features.margin_top,
        doc_features.margin_bottom,
        doc_features.margin_left,
        doc_features.margin_right,
        doc_features.line_spacing,
        doc_features.body_indent,
        doc_features.block_quote_indent,
    ]
    # section_count is always present
    numerical_mask = [
        1.0 if f is not None else 0.0 for f in numerical_fields
    ] + [1.0]

    # Font family: present if any slot is hot
    font_oh = features_to_font_onehot(doc_features)
    font_present = 1.0 if font_oh.sum() > 0 else 0.0
    font_mask = [font_present] * NUM_FONT_FAMILIES

    return np.array(numerical_mask + font_mask, dtype=np.float32)


# ---------------------------------------------------------------------------
# Dataset builders
# ---------------------------------------------------------------------------

def build_training_dataset(
    feature_list: list[Any],
    batch_size: int = 16,
    shuffle: bool = True,
) -> tf.data.Dataset:
    """Build a tf.data.Dataset of format feature tensors.

    Each element is a tensor of shape (NUM_FORMAT_FEATURES,).
    Suitable for training the StyleEncoder or AnomalyDetector.
    """
    arrays = [features_to_tensor(f) for f in feature_list]
    data = np.stack(arrays)
    dataset = tf.data.Dataset.from_tensor_slices(data)
    if shuffle:
        dataset = dataset.shuffle(buffer_size=max(len(feature_list), 1))
    dataset = dataset.batch(batch_size)
    return dataset


def build_classifier_dataset(
    feature_list: list[Any],
    jurisdiction_labels: list[int],
    court_level_labels: list[int],
    doc_type_labels: list[int],
    batch_size: int = 16,
    shuffle: bool = True,
) -> tf.data.Dataset:
    """Build a dataset for the FormatClassifier (multi-task).

    Returns dataset yielding:
        inputs: {"numerical_input": ..., "font_input": ...}
        outputs: {"jurisdiction": ..., "court_level": ..., "document_type": ...}
    """
    numerical = np.stack([features_to_numerical(f) for f in feature_list])
    fonts = np.stack([features_to_font_onehot(f) for f in feature_list])

    # One-hot encode labels
    jurisdictions = tf.one_hot(jurisdiction_labels, NUM_JURISDICTIONS)
    court_levels = tf.one_hot(court_level_labels, len(COURT_LEVELS))
    doc_types = tf.one_hot(doc_type_labels, len(DOCUMENT_TYPES))

    dataset = tf.data.Dataset.from_tensor_slices((
        {"numerical_input": numerical, "font_input": fonts},
        {"jurisdiction": jurisdictions, "court_level": court_levels,
         "document_type": doc_types},
    ))
    if shuffle:
        dataset = dataset.shuffle(buffer_size=max(len(feature_list), 1))
    dataset = dataset.batch(batch_size)
    return dataset


def build_heading_dataset(
    text_features: np.ndarray,
    format_features: np.ndarray,
    labels: np.ndarray,
    batch_size: int = 16,
    shuffle: bool = True,
) -> tf.data.Dataset:
    """Build a dataset for the HeadingClassifier.

    Args:
        text_features: (N, 5) - length, is_all_caps, starts_with_numeral, has_period, word_count
        format_features: (N, 4) - font_size, bold, centered, indent
        labels: (N,) - heading level 0-4

    Returns dataset yielding (combined_features, one_hot_labels).
    """
    combined = np.concatenate([text_features, format_features], axis=1)
    one_hot_labels = tf.one_hot(labels, 5)

    dataset = tf.data.Dataset.from_tensor_slices((
        combined.astype(np.float32),
        one_hot_labels,
    ))
    if shuffle:
        dataset = dataset.shuffle(buffer_size=max(len(labels), 1))
    dataset = dataset.batch(batch_size)
    return dataset


def build_predictor_dataset(
    feature_list: list[Any],
    jurisdiction_onehots: np.ndarray,
    mask_ratio: float = 0.3,
    batch_size: int = 16,
    shuffle: bool = True,
) -> tf.data.Dataset:
    """Build a dataset for the FormatPredictor.

    Randomly masks some features to create training pairs.
    The target is the full (unmasked) feature vector.

    Args:
        feature_list: list of DocumentFeatures
        jurisdiction_onehots: (N, NUM_JURISDICTIONS) array
        mask_ratio: proportion of features to randomly mask during training
    """
    full_features = np.stack([features_to_tensor(f) for f in feature_list])
    n_samples, n_features = full_features.shape

    # Generate random masks (1 = keep, 0 = mask)
    masks = (np.random.rand(n_samples, n_features) > mask_ratio).astype(np.float32)
    masked_features = full_features * masks

    dataset = tf.data.Dataset.from_tensor_slices((
        {
            "format_input": masked_features,
            "mask_input": masks,
            "jurisdiction_input": jurisdiction_onehots.astype(np.float32),
        },
        full_features,  # target is the full unmasked vector
    ))
    if shuffle:
        dataset = dataset.shuffle(buffer_size=max(n_samples, 1))
    dataset = dataset.batch(batch_size)
    return dataset
