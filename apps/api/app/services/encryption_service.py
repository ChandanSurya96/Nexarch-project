"""Envelope encryption for broker tokens (ADR-014, key versioning ADR-044).

Broker access/refresh tokens are the highest-sensitivity data Nexarch holds
(see docs/security.md). This module implements the envelope-encryption shape
security.md requires — a random data key per token, itself protected by a
master key — without a cloud KMS provisioned yet:

    data_key    = Fernet.generate_key()          # random, per token
    ciphertext  = Fernet(data_key).encrypt(plaintext)
    wrapped_key = Fernet(master_key).encrypt(data_key)
    stored      = "v{n}." + wrapped_key + "." + ciphertext

**Key versioning.** The stored value names the master-key version that
wrapped its data key. Without that marker — the format before ADR-044 was
just `wrapped_key + "." + ciphertext` — changing `ENCRYPTION_KMS_KEY_ID`
made every stored token permanently undecryptable, forcing every user to
reconnect their broker. That made the key un-rotatable in practice, which
is the same as having no incident response for a leaked key (ADR-043).

Because this is envelope encryption, rotation only has to re-wrap the small
data key; the token ciphertext itself is never decrypted or rewritten. See
scripts/rewrap_encryption_keys.py and docs/operations.md "Rotating
ENCRYPTION_KMS_KEY_ID".

Configuration (all read from the environment, never current_app — this
module is called from sync worker threads, which have no Flask app context):

    ENCRYPTION_KEYS                 "1:<secret>,2:<secret>"  (optional)
    ENCRYPTION_ACTIVE_KEY_VERSION   "2"                      (optional)
    ENCRYPTION_KMS_KEY_ID           "<secret>"               (version 1)

With only `ENCRYPTION_KMS_KEY_ID` set — the pre-ADR-044 configuration —
behaviour is unchanged: it is version 1, it is active, and values written
before versioning existed still decrypt. Nothing has to be reconfigured to
upgrade, and nothing has to be re-encrypted.

`ENCRYPTION_KMS_KEY_ID` remains a stand-in for a real KMS: swapping in
AWS/GCP KMS later means replacing only `_wrap_data_key`/`_unwrap_data_key`
with real KMS API calls — the per-record data-key shape stays the same. A
real KMS must back the master key before real user tokens are stored (see
docs/security.md's pre-launch checklist).

Decryption only ever happens inside the sync worker, at the moment of use
(see docs/security.md) — never in routes or schemas.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

# Values written before ADR-044 carry no version prefix. They were wrapped
# with whatever ENCRYPTION_KMS_KEY_ID held, which is version 1 by
# definition, so legacy ciphertext is readable without a data migration.
LEGACY_KEY_VERSION = 1


class EncryptionError(Exception):
    """Raised when a token can't be encrypted or decrypted."""


def _configured_keys() -> dict[int, str]:
    """Master secrets by version.

    ENCRYPTION_KEYS is the multi-key form used during a rotation;
    ENCRYPTION_KMS_KEY_ID is the single-key form and supplies version 1.
    Both may be set at once — that is exactly the state a rotation passes
    through — and ENCRYPTION_KEYS wins for any version it defines.
    """
    keys: dict[int, str] = {}

    single = os.environ.get("ENCRYPTION_KMS_KEY_ID", "").strip()
    if single:
        keys[LEGACY_KEY_VERSION] = single

    raw = os.environ.get("ENCRYPTION_KEYS", "").strip()
    for entry in (part.strip() for part in raw.split(",") if part.strip()):
        version_str, _, secret = entry.partition(":")
        if not secret.strip():
            raise EncryptionError(
                f"ENCRYPTION_KEYS entry {entry!r} is malformed — expected 'version:secret'."
            )
        try:
            version = int(version_str)
        except ValueError as exc:
            raise EncryptionError(
                f"ENCRYPTION_KEYS entry {entry!r} has a non-numeric version."
            ) from exc
        keys[version] = secret.strip()

    if not keys:
        raise EncryptionError(
            "No encryption key configured (set ENCRYPTION_KMS_KEY_ID or "
            "ENCRYPTION_KEYS) — cannot encrypt/decrypt broker tokens."
        )
    return keys


def _active_key_version() -> int:
    """The version new writes are wrapped with."""
    keys = _configured_keys()

    raw = os.environ.get("ENCRYPTION_ACTIVE_KEY_VERSION", "").strip()
    if not raw:
        # Highest configured version, so adding a key to ENCRYPTION_KEYS
        # without also setting the active version does the intuitive thing
        # rather than silently keeping the old key in use.
        return max(keys)

    try:
        version = int(raw)
    except ValueError as exc:
        raise EncryptionError(
            f"ENCRYPTION_ACTIVE_KEY_VERSION must be an integer, got {raw!r}."
        ) from exc

    if version not in keys:
        # Fail loudly at the point of use rather than writing tokens that
        # nothing can ever decrypt.
        raise EncryptionError(
            f"ENCRYPTION_ACTIVE_KEY_VERSION is {version} but no such key is "
            f"configured (have: {sorted(keys)})."
        )
    return version


def _secret_for_version(version: int) -> str:
    keys = _configured_keys()
    try:
        return keys[version]
    except KeyError as exc:
        raise EncryptionError(
            f"Stored token was wrapped with key version {version}, which is not "
            f"configured (have: {sorted(keys)}). Do not drop a key version until "
            f"every row has been re-wrapped — see docs/operations.md."
        ) from exc


def _fernet_from_secret(secret: str) -> Fernet:
    """Build a Fernet instance from an arbitrary secret string.

    Fernet keys must be 32 url-safe base64-encoded bytes. Rather than require
    the operator to hand-generate one, derive it from whatever secret string
    is configured, so any sufficiently long random string in .env works.
    """
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _wrap_data_key(data_key: bytes, version: int) -> bytes:
    """Encrypt a per-token data key with a master key (the KMS stand-in)."""
    return _fernet_from_secret(_secret_for_version(version)).encrypt(data_key)


def _unwrap_data_key(wrapped_key: bytes, version: int) -> bytes:
    return _fernet_from_secret(_secret_for_version(version)).decrypt(wrapped_key)


def _parse(stored: str) -> tuple[int, bytes, bytes]:
    """Split a stored value into (key_version, wrapped_key, ciphertext).

    Fernet tokens are url-safe base64 ('-' and '_', never '.'), so '.' is an
    unambiguous separator and the two formats can't be confused.
    """
    parts = stored.split(".")

    if len(parts) == 2:
        # Pre-ADR-044: "wrapped_key.ciphertext", implicitly version 1.
        return LEGACY_KEY_VERSION, parts[0].encode("ascii"), parts[1].encode("ascii")

    if len(parts) == 3 and parts[0].startswith("v"):
        try:
            version = int(parts[0][1:])
        except ValueError as exc:
            raise ValueError(f"bad key-version prefix {parts[0]!r}") from exc
        return version, parts[1].encode("ascii"), parts[2].encode("ascii")

    raise ValueError("stored value is not in a recognised encrypted-token format")


def encrypt_token(plaintext: str) -> str:
    """Encrypt a broker token for storage.

    Returns a single string safe to store in a Text column
    (`broker_connections.access_token_encrypted` / `refresh_token_encrypted`),
    tagged with the master-key version that wrapped its data key.
    """
    version = _active_key_version()
    data_key = Fernet.generate_key()
    ciphertext = Fernet(data_key).encrypt(plaintext.encode("utf-8"))
    wrapped_key = _wrap_data_key(data_key, version)
    return f"v{version}." + wrapped_key.decode("ascii") + "." + ciphertext.decode("ascii")


def decrypt_token(stored: str) -> str:
    """Decrypt a value previously produced by encrypt_token.

    Reads both the current versioned format and the pre-ADR-044 unversioned
    one, so no data migration is required to adopt key versioning.
    """
    try:
        version, wrapped_key_b, ciphertext_b = _parse(stored)
        data_key = _unwrap_data_key(wrapped_key_b, version)
        plaintext = Fernet(data_key).decrypt(ciphertext_b)
        return plaintext.decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise EncryptionError("Failed to decrypt token — invalid or tampered ciphertext.") from exc


def rewrap_token(stored: str, *, to_version: int | None = None) -> str:
    """Re-wrap a stored token's data key under a different master key.

    The whole point of envelope encryption: rotating the master key only
    requires unwrapping and re-wrapping the small data key. The token
    ciphertext is never decrypted, never re-encrypted, and is copied through
    byte-for-byte — so a rotation pass never holds a plaintext broker token
    in memory, and costs one Fernet operation per row rather than two.

    Returns the re-wrapped value. Used by scripts/rewrap_encryption_keys.py.
    """
    target = _active_key_version() if to_version is None else to_version

    try:
        version, wrapped_key_b, ciphertext_b = _parse(stored)
        data_key = _unwrap_data_key(wrapped_key_b, version)
    except (InvalidToken, ValueError) as exc:
        raise EncryptionError("Failed to re-wrap token — invalid or tampered ciphertext.") from exc

    rewrapped = _wrap_data_key(data_key, target)
    return f"v{target}." + rewrapped.decode("ascii") + "." + ciphertext_b.decode("ascii")


def key_version_of(stored: str) -> int:
    """Which master-key version a stored token is wrapped with.

    Lets an operator (and the rotation script) measure rotation progress
    without decrypting anything.
    """
    try:
        version, _, _ = _parse(stored)
    except ValueError as exc:
        raise EncryptionError("Not a recognised encrypted-token format.") from exc
    return version
