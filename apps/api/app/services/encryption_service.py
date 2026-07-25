"""Envelope encryption for broker tokens (ADR-014).

Broker access/refresh tokens are the highest-sensitivity data Nexarch holds
(see docs/security.md). This module implements the envelope-encryption shape
security.md requires — a random data key per token, itself protected by a
master key — without a cloud KMS provisioned yet:

    data_key    = Fernet.generate_key()          # random, per token
    ciphertext  = Fernet(data_key).encrypt(plaintext)
    wrapped_key = Fernet(master_key).encrypt(data_key)
    stored      = wrapped_key + b"." + ciphertext   # both base64url, '.'-joined

`ENCRYPTION_KMS_KEY_ID` (see .env.example) holds the master secret locally.
This is a stand-in for a real KMS: swapping in AWS/GCP KMS later means
replacing only `_wrap_data_key` / `_unwrap_data_key` with real KMS API calls —
the per-record data-key shape stays the same. This module is NOT
production-ready as-is; a real KMS must back the master key before real user
tokens are stored (see docs/security.md's pre-launch checklist).

Decryption only ever happens inside the sync worker, at the moment of use
(see docs/security.md) — never in routes or schemas.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken


class EncryptionError(Exception):
    """Raised when a token can't be encrypted or decrypted."""


def _master_secret() -> str:
    secret = os.environ.get("ENCRYPTION_KMS_KEY_ID", "")
    if not secret:
        raise EncryptionError(
            "ENCRYPTION_KMS_KEY_ID is not set — cannot encrypt/decrypt broker tokens."
        )
    return secret


def _fernet_from_secret(secret: str) -> Fernet:
    """Build a Fernet instance from an arbitrary secret string.

    Fernet keys must be 32 url-safe base64-encoded bytes. Rather than require
    the operator to hand-generate one, derive it from whatever secret string
    is configured, so any sufficiently long random string in .env works.
    """
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _wrap_data_key(data_key: bytes) -> bytes:
    """Encrypt a per-token data key with the master key (the KMS stand-in)."""
    return _fernet_from_secret(_master_secret()).encrypt(data_key)


def _unwrap_data_key(wrapped_key: bytes) -> bytes:
    return _fernet_from_secret(_master_secret()).decrypt(wrapped_key)


def encrypt_token(plaintext: str) -> str:
    """Encrypt a broker token for storage.

    Returns a single string safe to store in a Text column
    (`broker_connections.access_token_encrypted` / `refresh_token_encrypted`).
    """
    data_key = Fernet.generate_key()
    ciphertext = Fernet(data_key).encrypt(plaintext.encode("utf-8"))
    wrapped_key = _wrap_data_key(data_key)
    return wrapped_key.decode("ascii") + "." + ciphertext.decode("ascii")


def decrypt_token(stored: str) -> str:
    """Decrypt a value previously produced by encrypt_token."""
    try:
        wrapped_key_b, ciphertext_b = stored.split(".", 1)
        data_key = _unwrap_data_key(wrapped_key_b.encode("ascii"))
        plaintext = Fernet(data_key).decrypt(ciphertext_b.encode("ascii"))
        return plaintext.decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise EncryptionError("Failed to decrypt token — invalid or tampered ciphertext.") from exc
