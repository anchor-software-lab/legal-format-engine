"""Tests for TensorFlow model construction, forward pass, training, and save/load."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
import tensorflow as tf
from tensorflow import keras

from anchor_ml_engine.tf.models import (
    HEADING_TOTAL_FEATURES,
    NUM_COURT_LEVELS,
    NUM_DOCUMENT_TYPES,
    NUM_FONT_FAMILIES,
    NUM_FORMAT_FEATURES,
    NUM_HEADING_LEVELS,
    NUM_JURISDICTIONS,
    NUM_NUMERICAL_FEATURES,
    build_anomaly_detector,
    build_format_classifier,
    build_format_predictor,
    build_heading_classifier,
    build_style_encoder,
)


# ---------------------------------------------------------------------------
# Fixtures for synthetic data
# ---------------------------------------------------------------------------


@pytest.fixture
def batch_size():
    return 8


@pytest.fixture
def numerical_data(batch_size):
    return np.random.rand(batch_size, NUM_NUMERICAL_FEATURES).astype(np.float32)


@pytest.fixture
def font_data(batch_size):
    data = np.zeros((batch_size, NUM_FONT_FAMILIES), dtype=np.float32)
    for i in range(batch_size):
        data[i, np.random.randint(NUM_FONT_FAMILIES)] = 1.0
    return data


@pytest.fixture
def format_data(batch_size):
    return np.random.rand(batch_size, NUM_FORMAT_FEATURES).astype(np.float32)


@pytest.fixture
def heading_data(batch_size):
    return np.random.rand(batch_size, HEADING_TOTAL_FEATURES).astype(np.float32)


# ---------------------------------------------------------------------------
# 1. FormatClassifier
# ---------------------------------------------------------------------------


class TestFormatClassifier:
    def test_build(self):
        model = build_format_classifier()
        assert model.name == "format_classifier"
        assert len(model.outputs) == 3  # jurisdiction, court_level, document_type

    def test_forward_pass_shapes(self, numerical_data, font_data, batch_size):
        model = build_format_classifier()
        j, c, d = model.predict(
            {"numerical_input": numerical_data, "font_input": font_data},
            verbose=0,
        )
        assert j.shape == (batch_size, NUM_JURISDICTIONS)
        assert c.shape == (batch_size, NUM_COURT_LEVELS)
        assert d.shape == (batch_size, NUM_DOCUMENT_TYPES)

    def test_outputs_are_probabilities(self, numerical_data, font_data):
        model = build_format_classifier()
        j, c, d = model.predict(
            {"numerical_input": numerical_data, "font_input": font_data},
            verbose=0,
        )
        # Each row should sum to ~1 (softmax)
        np.testing.assert_allclose(j.sum(axis=1), 1.0, atol=1e-5)
        np.testing.assert_allclose(c.sum(axis=1), 1.0, atol=1e-5)
        np.testing.assert_allclose(d.sum(axis=1), 1.0, atol=1e-5)

    def test_train_small(self, numerical_data, font_data, batch_size):
        model = build_format_classifier()
        model.compile(
            optimizer="adam",
            loss="categorical_crossentropy",
        )
        j_labels = tf.one_hot(np.random.randint(0, NUM_JURISDICTIONS, batch_size), NUM_JURISDICTIONS)
        c_labels = tf.one_hot(np.random.randint(0, NUM_COURT_LEVELS, batch_size), NUM_COURT_LEVELS)
        d_labels = tf.one_hot(np.random.randint(0, NUM_DOCUMENT_TYPES, batch_size), NUM_DOCUMENT_TYPES)

        history = model.fit(
            {"numerical_input": numerical_data, "font_input": font_data},
            {"jurisdiction": j_labels, "court_level": c_labels, "document_type": d_labels},
            epochs=3,
            verbose=0,
        )
        assert len(history.history["loss"]) == 3

    def test_param_count(self):
        model = build_format_classifier()
        assert model.count_params() < 100_000

    def test_save_load(self, numerical_data, font_data):
        model = build_format_classifier()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "model.keras"
            model.save(str(path))
            loaded = keras.models.load_model(str(path))

        j1, c1, d1 = model.predict(
            {"numerical_input": numerical_data, "font_input": font_data}, verbose=0,
        )
        j2, c2, d2 = loaded.predict(
            {"numerical_input": numerical_data, "font_input": font_data}, verbose=0,
        )
        np.testing.assert_allclose(j1, j2, atol=1e-5)
        np.testing.assert_allclose(c1, c2, atol=1e-5)
        np.testing.assert_allclose(d1, d2, atol=1e-5)


# ---------------------------------------------------------------------------
# 2. StyleEncoder
# ---------------------------------------------------------------------------


class TestStyleEncoder:
    def test_build(self):
        autoencoder, encoder, decoder = build_style_encoder()
        assert autoencoder.name == "style_autoencoder"
        assert encoder.name == "style_encoder"
        assert decoder.name == "style_decoder"

    def test_forward_pass_shapes(self, format_data, batch_size):
        autoencoder, encoder, decoder = build_style_encoder(latent_dim=16)
        reconstructed = autoencoder.predict(format_data, verbose=0)
        assert reconstructed.shape == (batch_size, NUM_FORMAT_FEATURES)

        latent = encoder.predict(format_data, verbose=0)
        assert latent.shape == (batch_size, 16)

        decoded = decoder.predict(latent, verbose=0)
        assert decoded.shape == (batch_size, NUM_FORMAT_FEATURES)

    def test_train_small(self, format_data):
        autoencoder, _, _ = build_style_encoder()
        autoencoder.compile(optimizer="adam", loss="mse")
        history = autoencoder.fit(format_data, format_data, epochs=3, verbose=0)
        assert len(history.history["loss"]) == 3
        # Loss should decrease
        assert history.history["loss"][-1] <= history.history["loss"][0]

    def test_param_count(self):
        autoencoder, _, _ = build_style_encoder()
        assert autoencoder.count_params() < 100_000

    def test_save_load(self, format_data):
        autoencoder, encoder, decoder = build_style_encoder()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "encoder.keras"
            encoder.save(str(path))
            loaded = keras.models.load_model(str(path))

        e1 = encoder.predict(format_data, verbose=0)
        e2 = loaded.predict(format_data, verbose=0)
        np.testing.assert_allclose(e1, e2, atol=1e-5)


# ---------------------------------------------------------------------------
# 3. HeadingClassifier
# ---------------------------------------------------------------------------


class TestHeadingClassifier:
    def test_build(self):
        model = build_heading_classifier()
        assert model.name == "heading_classifier"

    def test_forward_pass_shapes(self, heading_data, batch_size):
        model = build_heading_classifier()
        pred = model.predict(heading_data, verbose=0)
        assert pred.shape == (batch_size, NUM_HEADING_LEVELS)

    def test_outputs_are_probabilities(self, heading_data):
        model = build_heading_classifier()
        pred = model.predict(heading_data, verbose=0)
        np.testing.assert_allclose(pred.sum(axis=1), 1.0, atol=1e-5)

    def test_train_small(self, heading_data, batch_size):
        model = build_heading_classifier()
        model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
        labels = tf.one_hot(np.random.randint(0, NUM_HEADING_LEVELS, batch_size), NUM_HEADING_LEVELS)
        history = model.fit(heading_data, labels, epochs=3, verbose=0)
        assert len(history.history["loss"]) == 3

    def test_param_count(self):
        model = build_heading_classifier()
        assert model.count_params() < 100_000


# ---------------------------------------------------------------------------
# 4. FormatPredictor
# ---------------------------------------------------------------------------


class TestFormatPredictor:
    def test_build(self):
        model = build_format_predictor()
        assert model.name == "format_predictor"

    def test_forward_pass_shapes(self, format_data, batch_size):
        model = build_format_predictor()
        masks = np.ones_like(format_data)
        jurisdictions = np.zeros((batch_size, NUM_JURISDICTIONS), dtype=np.float32)
        jurisdictions[:, 0] = 1.0

        pred = model.predict(
            {"format_input": format_data, "mask_input": masks,
             "jurisdiction_input": jurisdictions},
            verbose=0,
        )
        assert pred.shape == (batch_size, NUM_FORMAT_FEATURES)

    def test_train_small(self, format_data, batch_size):
        model = build_format_predictor()
        model.compile(optimizer="adam", loss="mse")

        masks = (np.random.rand(batch_size, NUM_FORMAT_FEATURES) > 0.3).astype(np.float32)
        jurisdictions = np.zeros((batch_size, NUM_JURISDICTIONS), dtype=np.float32)
        for i in range(batch_size):
            jurisdictions[i, np.random.randint(NUM_JURISDICTIONS)] = 1.0

        history = model.fit(
            {"format_input": format_data * masks, "mask_input": masks,
             "jurisdiction_input": jurisdictions},
            format_data,
            epochs=3,
            verbose=0,
        )
        assert len(history.history["loss"]) == 3

    def test_param_count(self):
        model = build_format_predictor()
        assert model.count_params() < 100_000


# ---------------------------------------------------------------------------
# 5. AnomalyDetector
# ---------------------------------------------------------------------------


class TestAnomalyDetector:
    def test_build(self):
        vae, encoder = build_anomaly_detector()
        assert vae.name == "anomaly_detector_vae"
        assert encoder.name == "vae_encoder"

    def test_forward_pass_shapes(self, format_data, batch_size):
        vae, encoder = build_anomaly_detector(latent_dim=8)
        reconstructed = vae.predict(format_data, verbose=0)
        assert reconstructed.shape == (batch_size, NUM_FORMAT_FEATURES)

        z_mean, z_log_var, z = encoder.predict(format_data, verbose=0)
        assert z_mean.shape == (batch_size, 8)
        assert z_log_var.shape == (batch_size, 8)
        assert z.shape == (batch_size, 8)

    def test_reconstruction_error(self, format_data):
        vae, _ = build_anomaly_detector()
        reconstructed = vae.predict(format_data, verbose=0)
        mse = np.mean((format_data - reconstructed) ** 2)
        # Just check it's a positive finite number
        assert mse >= 0.0
        assert np.isfinite(mse)

    def test_train_small(self, format_data):
        vae, _ = build_anomaly_detector()
        vae.compile(optimizer="adam")
        # VAE uses custom train_step expecting (x, y) tuples
        dataset = tf.data.Dataset.from_tensor_slices((format_data, format_data)).batch(4)
        history = vae.fit(dataset, epochs=3, verbose=0)
        assert len(history.history["loss"]) == 3

    def test_param_count(self):
        vae, _ = build_anomaly_detector()
        assert vae.count_params() < 100_000

    def test_save_load_encoder(self, format_data):
        """Test that the encoder (Functional model) saves and loads correctly."""
        _, encoder = build_anomaly_detector()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "encoder.keras"
            encoder.save(str(path))
            loaded = keras.models.load_model(str(path))

        z1, _, _ = encoder.predict(format_data, verbose=0)
        z2, _, _ = loaded.predict(format_data, verbose=0)
        np.testing.assert_allclose(z1, z2, atol=1e-5)
