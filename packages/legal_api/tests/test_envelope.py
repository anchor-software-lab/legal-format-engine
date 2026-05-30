"""Tests for envelope encryption primitives.

These are the security-critical pieces; tests pin behaviors that the
production wiring depends on (ciphertext doesn't leak plaintext,
tampering raises, wrong key raises, fresh nonce per call).
"""

from __future__ import annotations

import pytest

from legal_api.envelope import (
    DEK_BYTES,
    NONCE_BYTES,
    decrypt_document,
    encrypt_document,
    encrypt_for_upload,
    generate_dek,
    generate_keypair_pem,
    unwrap_dek,
    wrap_dek,
)


def test_dek_is_correct_size_and_random():
    a = generate_dek()
    b = generate_dek()
    assert len(a) == DEK_BYTES
    assert len(b) == DEK_BYTES
    assert a != b


def test_document_round_trip_recovers_plaintext():
    plaintext = b"the quick brown fox jumps over the lazy dog" * 100
    dek = generate_dek()
    ciphertext, nonce = encrypt_document(plaintext, dek)
    assert len(nonce) == NONCE_BYTES
    recovered = decrypt_document(ciphertext, nonce, dek)
    assert recovered == plaintext


def test_ciphertext_does_not_contain_plaintext_substrings():
    plaintext = b"PRIVILEGED AND CONFIDENTIAL " * 50
    dek = generate_dek()
    ciphertext, _ = encrypt_document(plaintext, dek)
    assert b"PRIVILEGED" not in ciphertext
    assert b"CONFIDENTIAL" not in ciphertext


def test_nonce_changes_per_encrypt_call():
    plaintext = b"x" * 1024
    dek = generate_dek()
    _, nonce_a = encrypt_document(plaintext, dek)
    _, nonce_b = encrypt_document(plaintext, dek)
    assert nonce_a != nonce_b


def test_decrypt_rejects_tampered_ciphertext():
    plaintext = b"hello"
    dek = generate_dek()
    ciphertext, nonce = encrypt_document(plaintext, dek)
    tampered = bytearray(ciphertext)
    tampered[0] ^= 0x01  # flip a bit
    with pytest.raises(Exception):  # cryptography raises InvalidTag
        decrypt_document(bytes(tampered), nonce, dek)


def test_decrypt_with_wrong_dek_fails():
    plaintext = b"hello"
    dek = generate_dek()
    wrong_dek = generate_dek()
    ciphertext, nonce = encrypt_document(plaintext, dek)
    with pytest.raises(Exception):
        decrypt_document(ciphertext, nonce, wrong_dek)


def test_dek_wrap_unwrap_round_trip():
    priv, pub = generate_keypair_pem()
    dek = generate_dek()
    wrapped = wrap_dek(dek, pub)
    assert wrapped != dek  # actually encrypted
    recovered = unwrap_dek(wrapped, priv)
    assert recovered == dek


def test_wrong_private_key_cannot_unwrap():
    _, pub_a = generate_keypair_pem()
    priv_b, _ = generate_keypair_pem()
    dek = generate_dek()
    wrapped = wrap_dek(dek, pub_a)
    with pytest.raises(Exception):
        unwrap_dek(wrapped, priv_b)


def test_encrypt_for_upload_full_round_trip():
    priv, pub = generate_keypair_pem()
    plaintext = b"a meaningful legal brief" * 1000
    payload = encrypt_for_upload(plaintext, pub)

    # Server side: unwrap with the private key, decrypt with the DEK.
    dek = unwrap_dek(payload.wrapped_dek, priv)
    recovered = decrypt_document(payload.ciphertext, payload.nonce, dek)
    assert recovered == plaintext


def test_encrypt_for_upload_payload_has_no_plaintext():
    priv, pub = generate_keypair_pem()
    plaintext = b"the secret string FOOBARBAZ"
    payload = encrypt_for_upload(plaintext, pub)
    for field in (payload.ciphertext, payload.nonce, payload.wrapped_dek):
        assert b"FOOBARBAZ" not in field


def test_encrypt_document_rejects_wrong_dek_length():
    with pytest.raises(ValueError, match="32 bytes"):
        encrypt_document(b"hi", b"too short")


def test_decrypt_document_rejects_wrong_nonce_length():
    dek = generate_dek()
    ciphertext, _ = encrypt_document(b"hi", dek)
    with pytest.raises(ValueError, match="12 bytes"):
        decrypt_document(ciphertext, b"short", dek)
