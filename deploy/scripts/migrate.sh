#!/usr/bin/env bash
# Schema-migration preflight, backup gate, post-validation and health evidence.
set -euo pipefail
BACKUP_GATE="${BRAIN_MIGRATION_BACKUP_GATE:-required}"
if [ "$BACKUP_GATE" = "required" ]; then
  test -f /srv/brain/backups/db.pg_dump || { echo "migration blocked: no verified backup" >&2; exit 1; }
fi
alembic upgrade head
alembic check
echo "migration_postvalidation=passed"
