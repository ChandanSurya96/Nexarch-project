"""Tests for app/services/encryption_service.py (ADR-014, ADR-044)."""

import base64
import hashlib

import pytest
from cryptography.fernet import Fernet

from app.services.encryption_service import (
    EncryptionError,
    decrypt_token,
    encrypt_token,
    key_version_of,
    rewrap_token,
)


def _encrypt_the_old_way(plaintext: str, secret: str) -> str:
    """Reproduce the exact pre-ADR-044 stored format.

    Copied deliberately rather than imported: the point is to pin the format
    real rows were written in before key versioning existed, so it has to
    stay fixed even as encryption_service changes. If this ever stops
    matching production data, that is the bug.
    """
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    master = Fernet(base64.urlsafe_b64encode(digest))
    data_key = Fernet.generate_key()
    ciphertext = Fernet(data_key).encrypt(plaintext.encode("utf-8"))
    return master.encrypt(data_key).decode("ascii") + "." + ciphertext.decode("ascii")


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

    def test_stored_value_is_version_wrapped_key_ciphertext(self):
        """Format changed in ADR-044 — it now names its key version."""
        stored = encrypt_token("token")
        parts = stored.split(".")
        assert len(parts) == 3
        assert parts[0] == "v1"


class TestTamperDetection:
    def test_tampered_ciphertext_raises(self):
        stored = encrypt_token("token")
        prefix, wrapped_key, ciphertext = stored.split(".")
        tampered = f"{prefix}.{wrapped_key}." + ciphertext[:-4] + "abcd"
        with pytest.raises(EncryptionError):
            decrypt_token(tampered)

    def test_garbage_input_raises(self):
        with pytest.raises(EncryptionError):
            decrypt_token("not-a-valid-stored-value")


class TestMissingMasterSecret:
    def test_encrypt_without_master_secret_raises(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KMS_KEY_ID", raising=False)
        monkeypatch.delenv("ENCRYPTION_KEYS", raising=False)
        with pytest.raises(EncryptionError):
            encrypt_token("token")

    def test_decrypt_without_master_secret_raises(self, monkeypatch):
        stored = encrypt_token("token")  # encrypt while the secret is still set
        monkeypatch.delenv("ENCRYPTION_KMS_KEY_ID", raising=False)
        monkeypatch.delenv("ENCRYPTION_KEYS", raising=False)
        with pytest.raises(EncryptionError):
            decrypt_token(stored)


OLD_KEY = "old-master-secret-at-least-32-characters-long"
NEW_KEY = "new-master-secret-at-least-32-characters-long"


@pytest.fixture()
def single_key(monkeypatch):
    """The pre-rotation configuration: one key, no ENCRYPTION_KEYS."""
    monkeypatch.setenv("ENCRYPTION_KMS_KEY_ID", OLD_KEY)
    monkeypatch.delenv("ENCRYPTION_KEYS", raising=False)
    monkeypatch.delenv("ENCRYPTION_ACTIVE_KEY_VERSION", raising=False)


class TestBackwardCompatibility:
    """Tokens written before key versioning must keep working, untouched.

    This is the requirement the whole design is subordinate to: adopting
    ADR-044 must not force a data migration and must not invalidate a single
    stored broker token. A failure here means every user reconnects.
    """

    def test_legacy_unversioned_token_still_decrypts(self, single_key):
        legacy = _encrypt_the_old_way("upstox-token-from-before-adr-044", OLD_KEY)
        assert legacy.count(".") == 1, "fixture should produce the old 2-part format"
        assert decrypt_token(legacy) == "upstox-token-from-before-adr-044"

    def test_legacy_token_is_treated_as_version_1(self, single_key):
        legacy = _encrypt_the_old_way("token", OLD_KEY)
        assert key_version_of(legacy) == 1

    def test_legacy_and_versioned_tokens_coexist(self, single_key):
        """A database mid-upgrade holds both formats at once."""
        legacy = _encrypt_the_old_way("old-token", OLD_KEY)
        modern = encrypt_token("new-token")

        assert decrypt_token(legacy) == "old-token"
        assert decrypt_token(modern) == "new-token"

    def test_unchanged_config_still_writes_version_1(self, single_key):
        """Upgrading the code alone must not change which key is in use."""
        assert key_version_of(encrypt_token("token")) == 1


class TestRotation:
    """Rotating the master key must require zero user reconnects."""

    def test_old_tokens_readable_after_new_key_becomes_active(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_KMS_KEY_ID", OLD_KEY)
        monkeypatch.delenv("ENCRYPTION_KEYS", raising=False)
        monkeypatch.delenv("ENCRYPTION_ACTIVE_KEY_VERSION", raising=False)
        before_rotation = encrypt_token("broker-token")
        legacy = _encrypt_the_old_way("legacy-token", OLD_KEY)

        # Step 1 of the runbook: add the new key, make it active, keep the old.
        monkeypatch.setenv("ENCRYPTION_KEYS", f"1:{OLD_KEY},2:{NEW_KEY}")
        monkeypatch.setenv("ENCRYPTION_ACTIVE_KEY_VERSION", "2")

        assert decrypt_token(before_rotation) == "broker-token"
        assert decrypt_token(legacy) == "legacy-token"
        assert key_version_of(encrypt_token("fresh")) == 2

    def test_rewrap_moves_a_token_to_the_active_key(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_KMS_KEY_ID", OLD_KEY)
        monkeypatch.delenv("ENCRYPTION_KEYS", raising=False)
        monkeypatch.delenv("ENCRYPTION_ACTIVE_KEY_VERSION", raising=False)
        original = encrypt_token("broker-token")

        monkeypatch.setenv("ENCRYPTION_KEYS", f"1:{OLD_KEY},2:{NEW_KEY}")
        monkeypatch.setenv("ENCRYPTION_ACTIVE_KEY_VERSION", "2")
        rewrapped = rewrap_token(original)

        assert key_version_of(rewrapped) == 2
        assert decrypt_token(rewrapped) == "broker-token"

    def test_rewrap_does_not_touch_the_ciphertext(self, monkeypatch):
        """Envelope encryption's payoff: only the data key is re-wrapped.

        The token ciphertext is copied byte-for-byte, so a rotation pass
        never holds a plaintext broker token in memory.
        """
        monkeypatch.setenv("ENCRYPTION_KEYS", f"1:{OLD_KEY},2:{NEW_KEY}")
        monkeypatch.setenv("ENCRYPTION_ACTIVE_KEY_VERSION", "1")
        original = encrypt_token("broker-token")

        monkeypatch.setenv("ENCRYPTION_ACTIVE_KEY_VERSION", "2")
        rewrapped = rewrap_token(original)

        assert original.split(".")[2] == rewrapped.split(".")[2]
        assert original.split(".")[1] != rewrapped.split(".")[1]

    def test_legacy_token_can_be_rewrapped(self, monkeypatch):
        legacy = _encrypt_the_old_way("legacy-token", OLD_KEY)

        monkeypatch.setenv("ENCRYPTION_KEYS", f"1:{OLD_KEY},2:{NEW_KEY}")
        monkeypatch.setenv("ENCRYPTION_ACTIVE_KEY_VERSION", "2")
        rewrapped = rewrap_token(legacy)

        assert key_version_of(rewrapped) == 2
        assert decrypt_token(rewrapped) == "legacy-token"

    def test_rollback_to_the_previous_key_still_reads_everything(self, monkeypatch):
        """Rollback path: revert the active version, both formats still read."""
        monkeypatch.setenv("ENCRYPTION_KEYS", f"1:{OLD_KEY},2:{NEW_KEY}")
        monkeypatch.setenv("ENCRYPTION_ACTIVE_KEY_VERSION", "2")
        written_under_v2 = encrypt_token("token-v2")

        monkeypatch.setenv("ENCRYPTION_ACTIVE_KEY_VERSION", "1")
        assert decrypt_token(written_under_v2) == "token-v2"
        assert key_version_of(encrypt_token("token-v1")) == 1

    def test_dropping_a_key_still_in_use_fails_loudly(self, monkeypatch):
        """The one genuinely dangerous operator mistake — name it clearly."""
        monkeypatch.setenv("ENCRYPTION_KEYS", f"1:{OLD_KEY},2:{NEW_KEY}")
        monkeypatch.setenv("ENCRYPTION_ACTIVE_KEY_VERSION", "1")
        stored = encrypt_token("token")

        monkeypatch.setenv("ENCRYPTION_KEYS", f"2:{NEW_KEY}")
        monkeypatch.delenv("ENCRYPTION_KMS_KEY_ID", raising=False)
        monkeypatch.setenv("ENCRYPTION_ACTIVE_KEY_VERSION", "2")

        with pytest.raises(EncryptionError, match="key version 1"):
            decrypt_token(stored)

    def test_active_version_with_no_configured_key_refuses_to_encrypt(self, monkeypatch):
        """Never write a token that nothing can decrypt."""
        monkeypatch.setenv("ENCRYPTION_KEYS", f"1:{OLD_KEY}")
        monkeypatch.delenv("ENCRYPTION_KMS_KEY_ID", raising=False)
        monkeypatch.setenv("ENCRYPTION_ACTIVE_KEY_VERSION", "9")

        with pytest.raises(EncryptionError, match="no such key is configured"):
            encrypt_token("token")

    def test_highest_version_is_active_by_default(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_KEYS", f"1:{OLD_KEY},2:{NEW_KEY}")
        monkeypatch.delenv("ENCRYPTION_ACTIVE_KEY_VERSION", raising=False)
        assert key_version_of(encrypt_token("token")) == 2
