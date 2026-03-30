"""Training routines for TensorFlow models.

Each trainer function builds a model, compiles it, trains on the provided data,
and saves checkpoints to ~/.anchor-ml-engine/models/.

All trainers support early stopping and learning rate scheduling.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import numpy as np
    import tensorflow as tf
    import keras
except ImportError:
    raise ImportError(
        "TensorFlow is required for anchor_ml_engine.tf.trainer. "
        "Install with: pip install anchor-ml-engine[tf]"
    )

from anchor_ml_engine.tf.models import (
    NUM_FORMAT_FEATURES,
    NUM_JURISDICTIONS,
    build_anomaly_detector,
    build_format_classifier,
    build_format_predictor,
    build_heading_classifier,
    build_style_encoder,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

MODEL_DIR = Path.home() / ".anchor-ml-engine" / "models"


def _ensure_model_dir(subdir: str) -> Path:
    """Create and return the model checkpoint directory."""
    path = MODEL_DIR / subdir
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Common callbacks
# ---------------------------------------------------------------------------


def _standard_callbacks(
    checkpoint_path: Path,
    monitor: str = "loss",
    patience: int = 10,
) -> list[keras.callbacks.Callback]:
    """Build standard training callbacks: checkpointing, early stopping, LR schedule."""
    return [
        keras.callbacks.ModelCheckpoint(
            filepath=str(checkpoint_path / "best_model.keras"),
            monitor=monitor,
            save_best_only=True,
            verbose=0,
        ),
        keras.callbacks.EarlyStopping(
            monitor=monitor,
            patience=patience,
            restore_best_weights=True,
            verbose=0,
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor=monitor,
            factor=0.5,
            patience=max(3, patience // 3),
            min_lr=1e-6,
            verbose=0,
        ),
    ]


# ---------------------------------------------------------------------------
# 1. FormatClassifier
# ---------------------------------------------------------------------------


def train_format_classifier(
    features: list[Any],
    jurisdiction_labels: list[int],
    court_level_labels: list[int],
    doc_type_labels: list[int],
    epochs: int = 50,
    batch_size: int = 16,
    validation_split: float = 0.2,
    **build_kwargs: Any,
) -> tuple[keras.Model, keras.callbacks.History]:
    """Train the multi-task FormatClassifier.

    Args:
        features: list of DocumentFeatures objects
        jurisdiction_labels: integer labels 0..63
        court_level_labels: integer labels 0..2
        doc_type_labels: integer labels 0..4
        epochs: max training epochs
        batch_size: training batch size
        validation_split: fraction held out for validation
        **build_kwargs: forwarded to build_format_classifier()

    Returns:
        (trained_model, training_history)
    """
    from anchor_ml_engine.tf.data_pipeline import (
        features_to_font_onehot,
        features_to_numerical,
    )

    model = build_format_classifier(**build_kwargs)
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss={
            "jurisdiction": "categorical_crossentropy",
            "court_level": "categorical_crossentropy",
            "document_type": "categorical_crossentropy",
        },
        metrics=["accuracy"],
    )

    # Prepare numpy arrays
    numerical = np.stack([features_to_numerical(f) for f in features])
    fonts = np.stack([features_to_font_onehot(f) for f in features])

    jurisdiction_oh = tf.one_hot(jurisdiction_labels, NUM_JURISDICTIONS).numpy()
    court_level_oh = tf.one_hot(court_level_labels, 3).numpy()
    doc_type_oh = tf.one_hot(doc_type_labels, 5).numpy()

    ckpt_path = _ensure_model_dir("format_classifier")
    callbacks = _standard_callbacks(ckpt_path, monitor="loss", patience=10)

    history = model.fit(
        {"numerical_input": numerical, "font_input": fonts},
        {"jurisdiction": jurisdiction_oh, "court_level": court_level_oh,
         "document_type": doc_type_oh},
        epochs=epochs,
        batch_size=batch_size,
        validation_split=validation_split,
        callbacks=callbacks,
        verbose=0,
    )

    model.save(str(ckpt_path / "final_model.keras"))
    return model, history


# ---------------------------------------------------------------------------
# 2. StyleEncoder
# ---------------------------------------------------------------------------


def train_style_encoder(
    features: list[Any],
    epochs: int = 100,
    batch_size: int = 16,
    latent_dim: int = 16,
    validation_split: float = 0.2,
) -> tuple[keras.Model, keras.Model, keras.Model, keras.callbacks.History]:
    """Train the StyleEncoder autoencoder.

    Args:
        features: list of DocumentFeatures objects
        epochs: max training epochs
        batch_size: training batch size
        latent_dim: dimensionality of the style embedding
        validation_split: fraction held out for validation

    Returns:
        (autoencoder, encoder, decoder, training_history)
    """
    from anchor_ml_engine.tf.data_pipeline import features_to_tensor

    autoencoder, encoder, decoder = build_style_encoder(latent_dim=latent_dim)
    autoencoder.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss="mse",
    )

    data = np.stack([features_to_tensor(f) for f in features])

    ckpt_path = _ensure_model_dir("style_encoder")
    callbacks = _standard_callbacks(ckpt_path, monitor="loss", patience=15)

    history = autoencoder.fit(
        data, data,  # input = target for autoencoder
        epochs=epochs,
        batch_size=batch_size,
        validation_split=validation_split,
        callbacks=callbacks,
        verbose=0,
    )

    autoencoder.save(str(ckpt_path / "autoencoder.keras"))
    encoder.save(str(ckpt_path / "encoder.keras"))
    decoder.save(str(ckpt_path / "decoder.keras"))
    return autoencoder, encoder, decoder, history


# ---------------------------------------------------------------------------
# 3. HeadingClassifier
# ---------------------------------------------------------------------------


def train_heading_classifier(
    text_features: np.ndarray,
    format_features: np.ndarray,
    labels: np.ndarray,
    epochs: int = 30,
    batch_size: int = 16,
    validation_split: float = 0.2,
    **build_kwargs: Any,
) -> tuple[keras.Model, keras.callbacks.History]:
    """Train the HeadingClassifier.

    Args:
        text_features: (N, 5) array - length, is_all_caps, starts_with_numeral,
                       has_period, word_count
        format_features: (N, 4) array - font_size, bold, centered, indent
        labels: (N,) integer array - heading level 0-4
        epochs: max training epochs
        batch_size: training batch size
        validation_split: fraction held out for validation

    Returns:
        (trained_model, training_history)
    """
    model = build_heading_classifier(**build_kwargs)
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )

    combined = np.concatenate(
        [text_features.astype(np.float32), format_features.astype(np.float32)],
        axis=1,
    )
    label_oh = tf.one_hot(labels.astype(np.int32), 5).numpy()

    ckpt_path = _ensure_model_dir("heading_classifier")
    callbacks = _standard_callbacks(ckpt_path, monitor="loss", patience=8)

    history = model.fit(
        combined, label_oh,
        epochs=epochs,
        batch_size=batch_size,
        validation_split=validation_split,
        callbacks=callbacks,
        verbose=0,
    )

    model.save(str(ckpt_path / "final_model.keras"))
    return model, history


# ---------------------------------------------------------------------------
# 4. FormatPredictor
# ---------------------------------------------------------------------------


def train_format_predictor(
    features: list[Any],
    jurisdiction_onehots: np.ndarray,
    epochs: int = 50,
    batch_size: int = 16,
    mask_ratio: float = 0.3,
    validation_split: float = 0.2,
    **build_kwargs: Any,
) -> tuple[keras.Model, keras.callbacks.History]:
    """Train the FormatPredictor with random masking.

    Args:
        features: list of DocumentFeatures objects
        jurisdiction_onehots: (N, 64) array of one-hot jurisdiction vectors
        epochs: max training epochs
        batch_size: training batch size
        mask_ratio: proportion of features to mask during training
        validation_split: fraction held out for validation

    Returns:
        (trained_model, training_history)
    """
    from anchor_ml_engine.tf.data_pipeline import features_to_tensor

    model = build_format_predictor(**build_kwargs)
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss="mse",
    )

    full_features = np.stack([features_to_tensor(f) for f in features])
    n_samples, n_features = full_features.shape

    # Random masks: 1 = keep, 0 = mask
    masks = (np.random.rand(n_samples, n_features) > mask_ratio).astype(np.float32)
    masked_features = full_features * masks

    ckpt_path = _ensure_model_dir("format_predictor")
    callbacks = _standard_callbacks(ckpt_path, monitor="loss", patience=10)

    history = model.fit(
        {
            "format_input": masked_features,
            "mask_input": masks,
            "jurisdiction_input": jurisdiction_onehots.astype(np.float32),
        },
        full_features,  # target is unmasked
        epochs=epochs,
        batch_size=batch_size,
        validation_split=validation_split,
        callbacks=callbacks,
        verbose=0,
    )

    model.save(str(ckpt_path / "final_model.keras"))
    return model, history


# ---------------------------------------------------------------------------
# 5. AnomalyDetector
# ---------------------------------------------------------------------------


def train_anomaly_detector(
    features: list[Any],
    epochs: int = 100,
    batch_size: int = 16,
    latent_dim: int = 8,
    validation_split: float = 0.2,
) -> tuple[keras.Model, keras.Model, keras.callbacks.History]:
    """Train the VAE-based AnomalyDetector.

    Args:
        features: list of DocumentFeatures objects
        epochs: max training epochs
        batch_size: training batch size
        latent_dim: VAE latent dimensionality
        validation_split: fraction held out for validation

    Returns:
        (vae_model, encoder_model, training_history)
    """
    from anchor_ml_engine.tf.data_pipeline import features_to_tensor

    vae, encoder = build_anomaly_detector(latent_dim=latent_dim)
    vae.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
    )

    data = np.stack([features_to_tensor(f) for f in features])

    # The VAE uses a custom train_step expecting (x, y) tuples
    n = len(data)
    n_val = max(1, int(n * validation_split))
    n_train = n - n_val

    train_ds = tf.data.Dataset.from_tensor_slices(
        (data[:n_train], data[:n_train])
    ).shuffle(n_train).batch(batch_size)
    val_ds = tf.data.Dataset.from_tensor_slices(
        (data[n_train:], data[n_train:])
    ).batch(batch_size)

    ckpt_path = _ensure_model_dir("anomaly_detector")
    callbacks = _standard_callbacks(ckpt_path, monitor="loss", patience=15)

    history = vae.fit(
        train_ds,
        validation_data=val_ds,
        epochs=epochs,
        callbacks=callbacks,
        verbose=0,
    )

    vae.save(str(ckpt_path / "vae.keras"))
    encoder.save(str(ckpt_path / "encoder.keras"))
    return vae, encoder, history
