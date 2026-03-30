"""Prediction and inference using trained TensorFlow models.

Provides a high-level API for:
- Jurisdiction/court/doc-type classification
- Format prediction (fill in missing features)
- Style encoding and similarity
- Anomaly detection
- Heading classification

Models are loaded lazily from ~/.anchor-ml-engine/models/ on first use.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import numpy as np
    import tensorflow as tf
    import keras
except ImportError:
    raise ImportError(
        "TensorFlow is required for legal_format_engine.ml.tf.predictor. "
        "Install with: pip install anchor-ml-engine[tf]"
    )

from legal_format_engine.ml.tf.models import (
    HEADING_TOTAL_FEATURES,
    NUM_FORMAT_FEATURES,
    NUM_JURISDICTIONS,
    NUM_NUMERICAL_FEATURES,
    NUM_FONT_FAMILIES,
)

MODEL_DIR = Path.home() / ".anchor-ml-engine" / "models"


# ---------------------------------------------------------------------------
# Lazy model loader
# ---------------------------------------------------------------------------


class _ModelCache:
    """Singleton cache for loaded models. Avoids reloading from disk."""

    def __init__(self) -> None:
        self._cache: dict[str, keras.Model] = {}

    def get(self, name: str, path: Path) -> keras.Model:
        """Load a model from disk if not already cached."""
        if name not in self._cache:
            if not path.exists():
                raise FileNotFoundError(
                    f"Model '{name}' not found at {path}. Train it first."
                )
            self._cache[name] = keras.models.load_model(path)
        return self._cache[name]

    def clear(self) -> None:
        """Clear the cache (useful for testing)."""
        self._cache.clear()

    def set(self, name: str, model: keras.Model) -> None:
        """Manually inject a model into the cache (for testing or direct use)."""
        self._cache[name] = model


_cache = _ModelCache()


def clear_model_cache() -> None:
    """Clear all cached models."""
    _cache.clear()


def set_model(name: str, model: keras.Model) -> None:
    """Inject a model into the cache for immediate use without loading from disk.

    Useful after training or in tests.
    """
    _cache.set(name, model)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_format_classifier() -> keras.Model:
    return _cache.get(
        "format_classifier",
        MODEL_DIR / "format_classifier" / "final_model.keras",
    )


def _load_style_encoder() -> keras.Model:
    return _cache.get(
        "style_encoder",
        MODEL_DIR / "style_encoder" / "encoder.keras",
    )


def _load_heading_classifier() -> keras.Model:
    return _cache.get(
        "heading_classifier",
        MODEL_DIR / "heading_classifier" / "final_model.keras",
    )


def _load_format_predictor() -> keras.Model:
    return _cache.get(
        "format_predictor",
        MODEL_DIR / "format_predictor" / "final_model.keras",
    )


def _load_anomaly_vae() -> keras.Model:
    return _cache.get(
        "anomaly_vae",
        MODEL_DIR / "anomaly_detector" / "vae.keras",
    )


# ---------------------------------------------------------------------------
# 1. Jurisdiction / court / doc-type classification
# ---------------------------------------------------------------------------


def predict_jurisdiction(
    features: Any,
    jurisdiction_list: list[str] | None = None,
) -> dict[str, Any]:
    """Predict jurisdiction, court level, and document type.

    Args:
        features: a DocumentFeatures object
        jurisdiction_list: optional list mapping indices to jurisdiction names

    Returns:
        dict with keys:
            jurisdiction_idx, jurisdiction_confidence,
            jurisdiction_name (if jurisdiction_list provided),
            court_level_idx, court_level_confidence,
            document_type_idx, document_type_confidence
    """
    from legal_format_engine.ml.tf.data_pipeline import (
        COURT_LEVELS,
        DOCUMENT_TYPES,
        features_to_font_onehot,
        features_to_numerical,
    )

    model = _load_format_classifier()

    numerical = features_to_numerical(features)[np.newaxis, :]
    font_oh = features_to_font_onehot(features)[np.newaxis, :]

    jurisdiction_pred, court_pred, doctype_pred = model.predict(
        {"numerical_input": numerical, "font_input": font_oh},
        verbose=0,
    )

    j_idx = int(np.argmax(jurisdiction_pred[0]))
    c_idx = int(np.argmax(court_pred[0]))
    d_idx = int(np.argmax(doctype_pred[0]))

    result: dict[str, Any] = {
        "jurisdiction_idx": j_idx,
        "jurisdiction_confidence": float(jurisdiction_pred[0][j_idx]),
        "court_level_idx": c_idx,
        "court_level": COURT_LEVELS[c_idx],
        "court_level_confidence": float(court_pred[0][c_idx]),
        "document_type_idx": d_idx,
        "document_type": DOCUMENT_TYPES[d_idx],
        "document_type_confidence": float(doctype_pred[0][d_idx]),
    }

    if jurisdiction_list and j_idx < len(jurisdiction_list):
        result["jurisdiction_name"] = jurisdiction_list[j_idx]

    return result


# ---------------------------------------------------------------------------
# 2. Format prediction (fill missing features)
# ---------------------------------------------------------------------------


def predict_format(
    partial_features: np.ndarray,
    mask: np.ndarray,
    jurisdiction_onehot: np.ndarray,
) -> np.ndarray:
    """Predict full format vector from partial (masked) features.

    Args:
        partial_features: (NUM_FORMAT_FEATURES,) array with 0 for missing values
        mask: (NUM_FORMAT_FEATURES,) array, 1=known 0=missing
        jurisdiction_onehot: (NUM_JURISDICTIONS,) one-hot jurisdiction vector

    Returns:
        (NUM_FORMAT_FEATURES,) predicted full format vector
    """
    model = _load_format_predictor()

    pred = model.predict(
        {
            "format_input": partial_features[np.newaxis, :].astype(np.float32),
            "mask_input": mask[np.newaxis, :].astype(np.float32),
            "jurisdiction_input": jurisdiction_onehot[np.newaxis, :].astype(np.float32),
        },
        verbose=0,
    )
    return pred[0]


# ---------------------------------------------------------------------------
# 3. Style encoding and similarity
# ---------------------------------------------------------------------------


def encode_style(features: Any) -> np.ndarray:
    """Encode a document's formatting as a style embedding vector.

    Args:
        features: a DocumentFeatures object

    Returns:
        latent embedding vector (shape depends on encoder config, typically 16-dim)
    """
    from legal_format_engine.ml.tf.data_pipeline import features_to_tensor

    encoder = _load_style_encoder()
    tensor = features_to_tensor(features)[np.newaxis, :]
    embedding = encoder.predict(tensor, verbose=0)
    return embedding[0]


def compute_style_similarity(
    embedding1: np.ndarray,
    embedding2: np.ndarray,
) -> float:
    """Compute cosine similarity between two style embeddings.

    Args:
        embedding1: style embedding vector
        embedding2: style embedding vector

    Returns:
        float in [-1, 1], where 1 = identical style
    """
    norm1 = np.linalg.norm(embedding1)
    norm2 = np.linalg.norm(embedding2)
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return float(np.dot(embedding1, embedding2) / (norm1 * norm2))


# ---------------------------------------------------------------------------
# 4. Anomaly detection
# ---------------------------------------------------------------------------


def detect_anomalies(
    features: Any,
) -> float:
    """Compute anomaly score for a document's formatting.

    Uses the VAE reconstruction error as the anomaly score.
    Higher score = more unusual formatting.

    Args:
        features: a DocumentFeatures object

    Returns:
        anomaly_score (float >= 0). Typical range 0-1 for normal,
        >1 for unusual formatting.
    """
    from legal_format_engine.ml.tf.data_pipeline import features_to_tensor

    vae = _load_anomaly_vae()
    tensor = features_to_tensor(features)[np.newaxis, :]
    reconstruction = vae.predict(tensor, verbose=0)
    mse = float(np.mean((tensor - reconstruction) ** 2))
    return mse


# ---------------------------------------------------------------------------
# 5. Heading classification
# ---------------------------------------------------------------------------


def classify_heading(
    text_features: np.ndarray,
    format_features: np.ndarray,
) -> dict[str, Any]:
    """Classify a heading's level from its text and format features.

    Args:
        text_features: (5,) array - length, is_all_caps, starts_with_numeral,
                       has_period, word_count
        format_features: (4,) array - font_size, bold, centered, indent

    Returns:
        dict with heading_level (int 0-4) and confidence (float)
    """
    model = _load_heading_classifier()
    combined = np.concatenate([
        text_features.astype(np.float32),
        format_features.astype(np.float32),
    ])[np.newaxis, :]

    pred = model.predict(combined, verbose=0)
    level = int(np.argmax(pred[0]))
    confidence = float(pred[0][level])

    return {
        "heading_level": level,
        "confidence": confidence,
        "probabilities": pred[0].tolist(),
    }
