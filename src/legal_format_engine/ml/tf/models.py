"""TensorFlow model definitions for document format learning.

All models are small (<100K params) since legal formatting is low-dimensional
data (< 50 features). Models use try/except for TF imports so the package
works without TensorFlow installed.
"""

from __future__ import annotations

try:
    import tensorflow as tf
    import keras
    from keras import layers
except ImportError:
    raise ImportError(
        "TensorFlow is required for legal_format_engine.ml.tf.models. "
        "Install with: pip install anchor-ml-engine[tf]"
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NUM_JURISDICTIONS = 64
NUM_COURT_LEVELS = 3  # trial, appellate, supreme
NUM_DOCUMENT_TYPES = 5  # brief, motion, memo, order, opinion
NUM_FONT_FAMILIES = 12  # one-hot encoded common fonts
NUM_HEADING_LEVELS = 5  # 0=not heading, 1-4

# Feature vector sizes
NUM_NUMERICAL_FEATURES = 9  # font_size, 4 margins, line_spacing, indent, block_quote_indent, body_indent
NUM_FORMAT_FEATURES = NUM_NUMERICAL_FEATURES + NUM_FONT_FAMILIES  # numerical + font one-hot
HEADING_TEXT_FEATURES = 5  # length, is_all_caps, starts_with_numeral, has_period, word_count
HEADING_FORMAT_FEATURES = 4  # font_size, bold, centered, indent
HEADING_TOTAL_FEATURES = HEADING_TEXT_FEATURES + HEADING_FORMAT_FEATURES


# ---------------------------------------------------------------------------
# 1. FormatClassifier - Multi-task classification
# ---------------------------------------------------------------------------

def build_format_classifier(
    num_numerical: int = NUM_NUMERICAL_FEATURES,
    num_font_classes: int = NUM_FONT_FAMILIES,
    backbone_units: tuple[int, ...] = (64, 32),
    dropout_rate: float = 0.3,
) -> keras.Model:
    """Build a multi-task format classifier.

    Inputs:
        numerical_input: (batch, num_numerical) - font_size, margins, etc.
        font_input: (batch, num_font_classes) - one-hot encoded font family

    Outputs:
        jurisdiction: (batch, 64) - softmax over jurisdictions
        court_level: (batch, 3) - softmax over court levels
        document_type: (batch, 5) - softmax over document types
    """
    numerical_input = keras.Input(shape=(num_numerical,), name="numerical_input")
    font_input = keras.Input(shape=(num_font_classes,), name="font_input")

    # Concatenate inputs
    x = layers.Concatenate()([numerical_input, font_input])

    # Shared backbone
    for units in backbone_units:
        x = layers.Dense(units)(x)
        x = layers.BatchNormalization()(x)
        x = layers.ReLU()(x)
        x = layers.Dropout(dropout_rate)(x)

    # Task-specific heads
    jurisdiction = layers.Dense(NUM_JURISDICTIONS, activation="softmax",
                                name="jurisdiction")(x)
    court_level = layers.Dense(NUM_COURT_LEVELS, activation="softmax",
                               name="court_level")(x)
    document_type = layers.Dense(NUM_DOCUMENT_TYPES, activation="softmax",
                                 name="document_type")(x)

    model = keras.Model(
        inputs=[numerical_input, font_input],
        outputs=[jurisdiction, court_level, document_type],
        name="format_classifier",
    )
    return model


# ---------------------------------------------------------------------------
# 2. StyleEncoder - Autoencoder for style embeddings
# ---------------------------------------------------------------------------

def build_style_encoder(
    input_dim: int = NUM_FORMAT_FEATURES,
    latent_dim: int = 16,
    encoder_units: tuple[int, ...] = (32,),
    decoder_units: tuple[int, ...] = (32,),
) -> tuple[keras.Model, keras.Model, keras.Model]:
    """Build a style autoencoder.

    Returns:
        (autoencoder, encoder, decoder) - three models sharing weights.
        encoder maps features -> latent embedding.
        decoder maps latent embedding -> reconstructed features.
        autoencoder is end-to-end for training.
    """
    # Encoder
    encoder_input = keras.Input(shape=(input_dim,), name="encoder_input")
    x = encoder_input
    for units in encoder_units:
        x = layers.Dense(units, activation="relu")(x)
    latent = layers.Dense(latent_dim, name="latent")(x)
    encoder = keras.Model(encoder_input, latent, name="style_encoder")

    # Decoder
    decoder_input = keras.Input(shape=(latent_dim,), name="decoder_input")
    x = decoder_input
    for units in decoder_units:
        x = layers.Dense(units, activation="relu")(x)
    decoded = layers.Dense(input_dim, name="reconstruction")(x)
    decoder = keras.Model(decoder_input, decoded, name="style_decoder")

    # Autoencoder (end-to-end)
    autoencoder_output = decoder(encoder(encoder_input))
    autoencoder = keras.Model(encoder_input, autoencoder_output,
                              name="style_autoencoder")

    return autoencoder, encoder, decoder


# ---------------------------------------------------------------------------
# 3. HeadingClassifier
# ---------------------------------------------------------------------------

def build_heading_classifier(
    input_dim: int = HEADING_TOTAL_FEATURES,
    hidden_units: tuple[int, ...] = (16, 8),
    dropout_rate: float = 0.2,
) -> keras.Model:
    """Build a heading level classifier.

    Input: text features + formatting features concatenated.
        text: (length, is_all_caps, starts_with_numeral, has_period, word_count)
        format: (font_size, bold, centered, indent)

    Output: (batch, 5) softmax - level 0 (not heading) through 4.
    """
    inp = keras.Input(shape=(input_dim,), name="heading_input")
    x = inp
    for units in hidden_units:
        x = layers.Dense(units, activation="relu")(x)
        x = layers.Dropout(dropout_rate)(x)
    output = layers.Dense(NUM_HEADING_LEVELS, activation="softmax",
                          name="heading_level")(x)

    model = keras.Model(inp, output, name="heading_classifier")
    return model


# ---------------------------------------------------------------------------
# 4. FormatPredictor - predict missing format features
# ---------------------------------------------------------------------------

def build_format_predictor(
    num_format_features: int = NUM_FORMAT_FEATURES,
    num_jurisdictions: int = NUM_JURISDICTIONS,
    hidden_units: tuple[int, ...] = (64, 32),
    dropout_rate: float = 0.2,
) -> keras.Model:
    """Build a format predictor with masked input handling.

    Inputs:
        format_input: (batch, num_format_features) - known features (0 for missing)
        mask_input: (batch, num_format_features) - 1 for known, 0 for missing
        jurisdiction_input: (batch, num_jurisdictions) - one-hot jurisdiction

    Output: (batch, num_format_features) - predicted full format vector.
    """
    format_input = keras.Input(shape=(num_format_features,), name="format_input")
    mask_input = keras.Input(shape=(num_format_features,), name="mask_input")
    jurisdiction_input = keras.Input(shape=(num_jurisdictions,),
                                     name="jurisdiction_input")

    # Multiply features by mask to zero out missing values explicitly
    masked_features = layers.Multiply()([format_input, mask_input])

    # Concatenate masked features, mask itself (so model knows what's missing),
    # and jurisdiction
    x = layers.Concatenate()([masked_features, mask_input, jurisdiction_input])

    for units in hidden_units:
        x = layers.Dense(units, activation="relu")(x)
        x = layers.Dropout(dropout_rate)(x)

    output = layers.Dense(num_format_features, name="predicted_format")(x)

    model = keras.Model(
        inputs=[format_input, mask_input, jurisdiction_input],
        outputs=output,
        name="format_predictor",
    )
    return model


# ---------------------------------------------------------------------------
# 5. AnomalyDetector - Variational Autoencoder
# ---------------------------------------------------------------------------

@keras.utils.register_keras_serializable(package="legal_format_engine")
class _Sampling(layers.Layer):
    """Reparameterization trick: sample z = mu + sigma * epsilon."""

    def call(self, inputs):
        z_mean, z_log_var = inputs
        batch = keras.ops.shape(z_mean)[0]
        dim = keras.ops.shape(z_mean)[1]
        epsilon = keras.random.normal(shape=(batch, dim))
        return z_mean + keras.ops.exp(0.5 * z_log_var) * epsilon


@keras.utils.register_keras_serializable(package="legal_format_engine")
class _VAE(keras.Model):
    """Variational Autoencoder as a keras.Model subclass.

    Keras 3 Functional models do not support ``add_loss()``, so the KL
    divergence term is added inside ``train_step`` / ``test_step`` instead.
    """

    def __init__(self, encoder: keras.Model, decoder: keras.Model, **kwargs):
        super().__init__(**kwargs)
        self.encoder = encoder
        self.decoder = decoder
        self.reconstruction_loss_tracker = keras.metrics.Mean(name="reconstruction_loss")
        self.kl_loss_tracker = keras.metrics.Mean(name="kl_loss")
        self.total_loss_tracker = keras.metrics.Mean(name="loss")

    @property
    def metrics(self):
        return [
            self.total_loss_tracker,
            self.reconstruction_loss_tracker,
            self.kl_loss_tracker,
        ]

    def call(self, inputs, training=False):
        z_mean, z_log_var, z = self.encoder(inputs, training=training)
        reconstruction = self.decoder(z, training=training)
        return reconstruction

    def _compute_losses(self, data):
        x, y = data
        z_mean, z_log_var, z = self.encoder(x, training=True)
        reconstruction = self.decoder(z, training=True)

        reconstruction_loss = keras.ops.mean(
            keras.ops.sum(keras.ops.square(y - reconstruction), axis=-1)
        )
        kl_loss = -0.5 * keras.ops.mean(
            keras.ops.sum(
                1 + z_log_var - keras.ops.square(z_mean) - keras.ops.exp(z_log_var),
                axis=-1,
            )
        )
        total_loss = reconstruction_loss + kl_loss
        return total_loss, reconstruction_loss, kl_loss

    def train_step(self, data):
        with tf.GradientTape() as tape:
            total_loss, reconstruction_loss, kl_loss = self._compute_losses(data)

        grads = tape.gradient(total_loss, self.trainable_weights)
        self.optimizer.apply_gradients(zip(grads, self.trainable_weights))

        self.total_loss_tracker.update_state(total_loss)
        self.reconstruction_loss_tracker.update_state(reconstruction_loss)
        self.kl_loss_tracker.update_state(kl_loss)

        return {m.name: m.result() for m in self.metrics}

    def test_step(self, data):
        total_loss, reconstruction_loss, kl_loss = self._compute_losses(data)

        self.total_loss_tracker.update_state(total_loss)
        self.reconstruction_loss_tracker.update_state(reconstruction_loss)
        self.kl_loss_tracker.update_state(kl_loss)

        return {m.name: m.result() for m in self.metrics}

    def get_config(self):
        base = super().get_config()
        base["encoder"] = keras.saving.serialize_keras_object(self.encoder)
        base["decoder"] = keras.saving.serialize_keras_object(self.decoder)
        return base

    @classmethod
    def from_config(cls, config):
        encoder = keras.saving.deserialize_keras_object(config.pop("encoder"))
        decoder = keras.saving.deserialize_keras_object(config.pop("decoder"))
        return cls(encoder=encoder, decoder=decoder, **config)


def build_anomaly_detector(
    input_dim: int = NUM_FORMAT_FEATURES,
    latent_dim: int = 8,
    encoder_units: tuple[int, ...] = (32,),
    decoder_units: tuple[int, ...] = (32,),
) -> tuple[keras.Model, keras.Model]:
    """Build a VAE-based anomaly detector.

    Returns:
        (vae_model, encoder_model)

    The VAE loss = reconstruction_loss + KL_divergence.
    Anomaly score = reconstruction error on a given sample.
    """
    # Encoder
    encoder_input = keras.Input(shape=(input_dim,), name="vae_input")
    x = encoder_input
    for units in encoder_units:
        x = layers.Dense(units, activation="relu")(x)

    z_mean = layers.Dense(latent_dim, name="z_mean")(x)
    z_log_var = layers.Dense(latent_dim, name="z_log_var")(x)
    z = _Sampling()([z_mean, z_log_var])

    encoder = keras.Model(encoder_input, [z_mean, z_log_var, z],
                          name="vae_encoder")

    # Decoder
    decoder_input = keras.Input(shape=(latent_dim,))
    x = decoder_input
    for units in decoder_units:
        x = layers.Dense(units, activation="relu")(x)
    decoder_output = layers.Dense(input_dim, name="vae_reconstruction")(x)
    decoder = keras.Model(decoder_input, decoder_output, name="vae_decoder")

    # VAE end-to-end (subclassed model for custom train_step with KL loss)
    vae = _VAE(encoder=encoder, decoder=decoder, name="anomaly_detector_vae")
    # Build the model by calling it once
    vae(keras.ops.zeros((1, input_dim)))

    return vae, encoder
