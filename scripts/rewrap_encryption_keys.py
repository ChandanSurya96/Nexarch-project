"""Re-wrap stored broker tokens under a new master key version (ADR-044).

Run from the project root with the apps/api venv active:

    # See what would change — no writes.
    apps/api/venv/Scripts/python.exe scripts/rewrap_encryption_keys.py --status
    apps/api/venv/Scripts/python.exe scripts/rewrap_encryption_keys.py --dry-run

    # Do it.
    apps/api/venv/Scripts/python.exe scripts/rewrap_encryption_keys.py --apply

Step 3 of "Rotating ENCRYPTION_KMS_KEY_ID" in docs/operations.md. Before
running with --apply, both the old and new keys must be configured:

    ENCRYPTION_KEYS="1:<old secret>,2:<new secret>"
    ENCRYPTION_ACTIVE_KEY_VERSION="2"

Because this is envelope encryption, only each row's small data key is
unwrapped and re-wrapped — the token ciphertext is copied byte-for-byte and
never decrypted. A rotation pass therefore never holds a plaintext broker
token in memory, and a crash midway leaves a mix of key versions, which is
a state the application reads perfectly well. It is safe to re-run.

Do NOT remove the old key from ENCRYPTION_KEYS until --status reports zero
rows remaining on it. Removing it early is the one irreversible mistake
available here: the data keys become unrecoverable and every affected user
must reconnect their broker.
"""

import argparse
import os
import sys
from collections import Counter
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent / "apps" / "api"
sys.path.insert(0, str(API_DIR))
os.chdir(API_DIR)

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.broker_connection import BrokerConnection  # noqa: E402
from app.services.encryption_service import (  # noqa: E402
    EncryptionError,
    _active_key_version,
    key_version_of,
    rewrap_token,
)

# Both columns hold envelope-encrypted values; refresh_token_encrypted is
# nullable (not every broker issues one).
TOKEN_COLUMNS = ("access_token_encrypted", "refresh_token_encrypted")


def _versions_in_use() -> tuple[Counter, set]:
    """Count tokens per key version, and note which versions can't be read.

    "Readable" is verified by actually unwrapping, not by checking whether a
    version appears in ENCRYPTION_KEYS. key_version_of() only parses the
    stored prefix — it needs no key at all — so a version whose key is
    missing, or whose key is present but *wrong*, still counts as that
    version. Both cases were mistaken for healthy in a first draft of this
    script, which is exactly the mistake that ends with unrecoverable data.
    """
    counts: Counter = Counter()
    unreadable: set = set()

    for connection in BrokerConnection.query.all():
        for column in TOKEN_COLUMNS:
            stored = getattr(connection, column)
            if not stored:
                continue
            try:
                version = key_version_of(stored)
            except EncryptionError:
                counts["malformed"] += 1
                unreadable.add("malformed")
                continue

            counts[version] += 1
            if version not in unreadable:
                try:
                    # Cheap: unwraps the data key only, never the token.
                    rewrap_token(stored, to_version=version)
                except EncryptionError:
                    unreadable.add(version)

    return counts, unreadable


def _report(target: int) -> tuple[Counter, set]:
    counts, unreadable = _versions_in_use()
    if not counts:
        print("No encrypted broker tokens stored — nothing to rotate.")
        return counts, unreadable

    print(f"\nActive key version: {target}\n")
    print(f"{'key version':<16}{'tokens':>8}  status")
    print("-" * 40)
    for version, count in sorted(counts.items(), key=lambda kv: str(kv[0])):
        if version in unreadable:
            status = "UNREADABLE - key missing or wrong"
        elif version == target:
            status = "active"
        else:
            status = "readable, awaiting re-wrap"
        print(f"{str(version):<16}{count:>8}  {status}")

    stale = sum(count for version, count in counts.items() if version != target)
    print(f"\n{stale} token(s) not yet on the active key.")

    if unreadable:
        print(
            f"\nWARNING: key version(s) {sorted(unreadable, key=str)} cannot decrypt their "
            "own tokens. Fix the configuration before doing anything else — re-wrapping "
            "cannot proceed, and retiring a key in this state is unrecoverable."
        )
    return counts, unreadable


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status", action="store_true", help="report key versions in use")
    mode.add_argument("--dry-run", action="store_true", help="report what --apply would change")
    mode.add_argument("--apply", action="store_true", help="re-wrap and commit")
    args = parser.parse_args()

    app = create_app(os.environ.get("FLASK_ENV", "development"))

    with app.app_context():
        try:
            target = _active_key_version()
        except EncryptionError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

        counts, unreadable = _report(target)
        if args.status:
            return 1 if unreadable else 0
        if unreadable:
            print(
                "\nRefusing to proceed while some tokens cannot be decrypted — "
                "configure the correct key for every version listed above first.",
                file=sys.stderr,
            )
            return 1

        rewrapped = 0
        failed = 0
        for connection in BrokerConnection.query.all():
            for column in TOKEN_COLUMNS:
                stored = getattr(connection, column)
                if not stored or key_version_of(stored) == target:
                    continue
                try:
                    if args.apply:
                        setattr(connection, column, rewrap_token(stored, to_version=target))
                    rewrapped += 1
                except EncryptionError as exc:
                    failed += 1
                    print(
                        f"  FAILED {connection.id} {column}: {exc}",
                        file=sys.stderr,
                    )

        if args.dry_run:
            db.session.rollback()
            print(f"\nDRY RUN — would re-wrap {rewrapped} token(s). Nothing written.")
            return 1 if failed else 0

        if failed:
            db.session.rollback()
            print(
                f"\n{failed} token(s) failed to re-wrap — rolled back, nothing written.",
                file=sys.stderr,
            )
            return 1

        db.session.commit()
        print(f"\nRe-wrapped {rewrapped} token(s) to key version {target}.")
        print("Verify with --status, then remove the retired key from ENCRYPTION_KEYS.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
