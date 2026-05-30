"""Envelope-encryption primitives for the SaaS upload flow.

Two layers:

- `generate_dek` / `encrypt_document` / `decrypt_document` — AES-256-GCM
  on the document bytes. Each document gets a fresh random Data
  Encryption Key (DEK); the cipher binds the ciphertext to a random
  96-bit nonce.
- `wrap_dek` / `unwrap_dek` — RSA-OAEP(SHA-256) on the DEK. The DEK
  is wrapped with the org's public key; only the holder of the
  matching private key can unwrap it.

The customer-managed model: the org generates the RSA keypair and
holds the private key. The server only ever sees the public key,
the ciphertext, the random nonce, and the wrapped DEK. To process a
document, the server requests a session unwrap from the
EnvelopeKeyring (production: callback to the customer's plugin;
tests / v1 alpha: in-memory holder of the private key).

Pure functions; no I/O, no global state. Tests in test_envelope.py
pin the round-trip and the "ciphertext doesn't contain plaintext"
property.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


DEK_BYTES = 32  # AES-256
NONCE_BYTES = 12  # AES-GCM standard
RSA_KEY_SIZE_BITS = 3072  # 128-bit security; OAEP(SHA-256) compatible


@dataclass(frozen=True)
class EncryptedPayload:
    """Wire shape for an encrypted document upload."""

    ciphertext: bytes
    nonce: bytes
    wrapped_dek: bytes


def generate_dek() -> bytes:
    return os.urandom(DEK_BYTES)


def encrypt_document(plaintext: bytes, dek: bytes) -> tuple[bytes, bytes]:
    """AES-256-GCM encrypt. Returns (ciphertext, nonce).

    The 96-bit nonce must be unique for a given DEK; since we generate
    a fresh DEK per document, a fresh nonce per encrypt() call is
    sufficient. The auth tag is appended to the ciphertext by AESGCM.
    """
    if len(dek) != DEK_BYTES:
        raise ValueError(f"DEK must be {DEK_BYTES} bytes")
    nonce = os.urandom(NONCE_BYTES)
    aesgcm = AESGCM(dek)
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data=None)
    return ciphertext, nonce


def decrypt_document(ciphertext: bytes, nonce: bytes, dek: bytes) -> bytes:
    if len(dek) != DEK_BYTES:
        raise ValueError(f"DEK must be {DEK_BYTES} bytes")
    if len(nonce) != NONCE_BYTES:
        raise ValueError(f"nonce must be {NONCE_BYTES} bytes")
    aesgcm = AESGCM(dek)
    return aesgcm.decrypt(nonce, ciphertext, associated_data=None)


def generate_keypair_pem() -> tuple[bytes, bytes]:
    """Generate a fresh RSA keypair, return (private_pem, public_pem).

    PKCS#8 private key, SubjectPublicKeyInfo public key, both PEM.
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=RSA_KEY_SIZE_BITS
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def wrap_dek(dek: bytes, public_key_pem: bytes) -> bytes:
    """RSA-OAEP(SHA-256) encrypt a DEK with an org public key."""
    public_key = serialization.load_pem_public_key(public_key_pem)
    return public_key.encrypt(
        dek,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )


def unwrap_dek(wrapped_dek: bytes, private_key_pem: bytes) -> bytes:
    """RSA-OAEP(SHA-256) decrypt a wrapped DEK with the org private key."""
    private_key = serialization.load_pem_private_key(
        private_key_pem, password=None
    )
    return private_key.decrypt(
        wrapped_dek,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )


def encrypt_for_upload(
    plaintext: bytes, org_public_key_pem: bytes
) -> EncryptedPayload:
    """Convenience for clients: generate DEK, encrypt, wrap, package.

    The plaintext and DEK are zeroed by Python's GC; callers that need
    stronger guarantees should pin their own buffers.
    """
    dek = generate_dek()
    ciphertext, nonce = encrypt_document(plaintext, dek)
    wrapped_dek = wrap_dek(dek, org_public_key_pem)
    return EncryptedPayload(
        ciphertext=ciphertext,
        nonce=nonce,
        wrapped_dek=wrapped_dek,
    )
