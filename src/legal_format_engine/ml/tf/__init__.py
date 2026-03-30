"""TensorFlow-based ML models for document format learning.

This is an optional enhancement layer. The base anchor-ml-engine works
with pure statistical methods; TF provides neural network models for:

- FormatClassifier: multi-task classification of jurisdiction/court/doc type
- StyleEncoder: autoencoder that maps format features to a style embedding
- HeadingClassifier: classify text+format features into heading levels
- FormatPredictor: predict missing format features given partial input
- AnomalyDetector: VAE-based anomaly detection for unusual formatting

Install with: pip install anchor-ml-engine[tf]
"""

from __future__ import annotations

_TF_AVAILABLE = False
try:
    import tensorflow as tf  # noqa: F401
    _TF_AVAILABLE = True
except ImportError:
    pass


def is_tf_available() -> bool:
    """Check whether TensorFlow is installed and importable."""
    return _TF_AVAILABLE


__all__ = [
    "is_tf_available",
    "models",
    "trainer",
    "predictor",
    "data_pipeline",
]
