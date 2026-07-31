#!/usr/bin/env bash
# Postgres restore + verification (ADR-042). See docs/operations.md.
#
# Two uses, and they matter equally:
#   1. Real recovery during an incident.
#   2. The routine drill that proves a backup is restorable BEFORE you need
#      it. Most backup systems fail at restore time, not at backup time.
#
# Usage:
#   ./scripts/restore_db.sh <dump-file> <target-database-url>
#
# Refuses to run against a URL that looks like production unless
# ALLOW_PRODUCTION_RESTORE=yes is set, because the whole point of a drill is
# to restore somewhere safe, and a mistyped target during practice would be a
# self-inflicted outage.

set -euo pipefail

DUMP_FILE="${1:-}"
TARGET_URL="${2:-}"

if [[ -z "$DUMP_FILE" || -z "$TARGET_URL" ]]; then
  echo "Usage: $0 <dump-file> <target-database-url>" >&2
  exit 1
fi

[[ -f "$DUMP_FILE" ]] || { echo "ERROR: no such file: $DUMP_FILE" >&2; exit 1; }

command -v pg_restore >/dev/null 2>&1 || {
  echo "ERROR: pg_restore not found. Install the postgresql-client package." >&2
  exit 1
}

# Guard against restoring over production by accident.
if [[ "$TARGET_URL" == *"prod"* || "$TARGET_URL" == *"production"* ]]; then
  if [[ "${ALLOW_PRODUCTION_RESTORE:-}" != "yes" ]]; then
    echo "REFUSING: target looks like production." >&2
    echo "  A restore DESTROYS the target's current contents." >&2
    echo "  If this is a real recovery, re-run with ALLOW_PRODUCTION_RESTORE=yes" >&2
    exit 1
  fi
  echo "!!! Restoring into a PRODUCTION-looking target in 5s. Ctrl-C to abort."
  sleep 5
fi

# Verify integrity first — restoring a corrupted dump wastes the window you
# least want to waste.
CHECKSUM_FILE="${DUMP_FILE}.sha256"
if [[ -f "$CHECKSUM_FILE" ]]; then
  echo "Verifying checksum ..."
  # -c, not --check: GNU coreutils accepts both, but BusyBox (Alpine, and
  # therefore the postgres:*-alpine images) only understands -c. Found by
  # running this drill inside the container rather than assuming.
  if command -v sha256sum >/dev/null 2>&1; then
    (cd "$(dirname "$CHECKSUM_FILE")" && sha256sum -c "$(basename "$CHECKSUM_FILE")")
  else
    (cd "$(dirname "$CHECKSUM_FILE")" && shasum -a 256 -c "$(basename "$CHECKSUM_FILE")")
  fi
else
  echo "WARNING: no checksum file alongside the dump; integrity unverified."
fi

echo "Restoring ${DUMP_FILE} -> target ..."

# --clean --if-exists: drop existing objects first so the restore is
#   deterministic rather than merging into whatever was already there.
# --single-transaction: all-or-nothing; a failure part-way leaves the target
#   untouched instead of half-restored.
# --no-owner/--no-privileges: match how the dump was taken.
pg_restore \
  --dbname="$TARGET_URL" \
  --clean --if-exists \
  --single-transaction \
  --no-owner \
  --no-privileges \
  "$DUMP_FILE"

echo
echo "Restore complete. Verifying ..."

# Row counts on the tables that actually carry user data. A restore that
# "succeeds" into an empty database is the classic silent failure.
psql "$TARGET_URL" --tuples-only --command "
SELECT 'users: '            || count(*) FROM users
UNION ALL SELECT 'portfolios: '        || count(*) FROM portfolios
UNION ALL SELECT 'holdings: '          || count(*) FROM holdings
UNION ALL SELECT 'portfolio_snapshots: '|| count(*) FROM portfolio_snapshots
UNION ALL SELECT 'broker_connections: '|| count(*) FROM broker_connections
UNION ALL SELECT 'follows: '           || count(*) FROM follows
UNION ALL SELECT 'audit_logs: '        || count(*) FROM audit_logs;
"

echo
echo "Compare these counts against the source. Also confirm schema version:"
echo "  psql \"\$TARGET_URL\" -c 'SELECT version_num FROM alembic_version;'"
echo
echo "NOTE: broker access tokens in the restored data are encrypted with"
echo "whatever ENCRYPTION_KMS_KEY_ID was current when they were written."
echo "Restoring into an environment with a different key leaves them"
echo "undecryptable — see docs/operations.md 'Secret rotation'."
