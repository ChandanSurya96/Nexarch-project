"""Tests for app/services/encryption_service.py (ADR-014)."""

import pytest

from app.services.encryption_service import EncryptionError, decrypt_token, encrypt_token


class TestEncryptionRoundTrip:
    def test_round_trip(self):
        plaintext = "upstox-access-token-abc123"
        stored = encrypt_token(plaintext)
        assert decrypt_token(stored) == plaintext

    def test_ciphertext_differs_each_time(self):
        # A fresh random data key per call means two encryptions of the same
        # plaintext must not be byte-identical.
        stored_a = encrypt_token("same-plaintext")
        stored_b = encrypt_token("same-plaintext")
        assert stored_a != stored_b
        assert decrypt_token(stored_a) == "same-plaintext"
        assert decrypt_token(stored_b) == "same-plaintext"

    def test_stored_value_is_wrapped_key_dot_ciphertext(self):
        stored = encrypt_token("token")
        parts = stored.split(".")
        assert len(parts) == 2


class TestTamperDetection:
    def test_tampered_ciphertext_raises(self):
        stored = encrypt_token("token")
        wrapped_key, ciphertext = stored.split(".", 1)
        tampered = wrapped_key + "." + ciphertext[:-4] + "abcd"
        with pytest.raises(EncryptionError):
            decrypt_token(tampered)

    def test_garbage_input_raises(self):
        with pytest.raises(EncryptionError):
            decrypt_token("not-a-valid-stored-value")


class TestMissingMasterSecret:
    def test_encrypt_without_master_secret_raises(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KMS_KEY_ID", raising=False)
        with pytest.raises(EncryptionError):
            encrypt_token("token")

    def test_decrypt_without_master_secret_raises(self, monkeypatch):
        stored = encrypt_token("token")  # encrypt while the secret is still set
        monkeypatch.delenv("ENCRYPTION_KMS_KEY_ID", raising=False)
        with pytest.raises(EncryptionError):
            decrypt_token(stored)
