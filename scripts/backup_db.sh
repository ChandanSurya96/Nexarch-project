#!/usr/bin/env bash
# Postgres logical backup (ADR-042). See docs/operations.md.
#
# Railway's managed Postgres takes its own automated backups; this exists for
# the things those don't cover: a backup you can restore somewhere else, a
# pre-migration safety copy you control, and — most importantly — an artifact
# you can actually practise restoring. A backup nobody has restored is a
# hypothesis, not a backup.
#
# Usage:
#   DATABASE_URL=postgresql://user:pw@host:5432/db ./scripts/backup_db.sh [outdir]
#
# Produces a timestamped custom-format dump (pg_restore-compatible,
# compressed, selective-restore capable) plus a SHA-256 checksum.

set -euo pipefail

OUT_DIR="${1:-./backups}"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL is not set." >&2
  echo "  Never hardcode it here — pass it in from your secret store." >&2
  exit 1
fi

command -v pg_dump >/dev/null 2>&1 || {
  echo "ERROR: pg_dump not found. Install the postgresql-client package." >&2
  exit 1
}

mkdir -p "$OUT_DIR"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DUMP_FILE="${OUT_DIR}/nexarch-${TIMESTAMP}.dump"

echo "Backing up to ${DUMP_FILE} ..."

# --format=custom: compressed and restorable table-by-table.
# --no-owner/--no-privileges: portable across environments, so a production
#   dump can be restored into a local scratch database for a drill without
#   role errors.
pg_dump \
  --dbname="$DATABASE_URL" \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file="$DUMP_FILE"

# Checksum so a silently-truncated or corrupted transfer is detectable before
# you're relying on the file during an incident.
#
# Recorded against the BASENAME, not the full path, so the dump and its
# checksum stay a portable pair — copy both to another machine (or a
# different directory) and verification still works.
DUMP_NAME="$(basename "$DUMP_FILE")"
if command -v sha256sum >/dev/null 2>&1; then
  (cd "$OUT_DIR" && sha256sum "$DUMP_NAME" > "${DUMP_NAME}.sha256")
else
  (cd "$OUT_DIR" && shasum -a 256 "$DUMP_NAME" > "${DUMP_NAME}.sha256")
fi

SIZE="$(du -h "$DUMP_FILE" | cut -f1)"
echo "Done: ${DUMP_FILE} (${SIZE})"
echo "Checksum: ${DUMP_FILE}.sha256"
echo
echo "This backup is unverified until it has been restored."
echo "Run: ./scripts/restore_db.sh ${DUMP_FILE} <scratch-database-url>"
