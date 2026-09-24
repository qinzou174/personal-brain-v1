#!/usr/bin/env bash
# Wrapper exporting all required env vars then running backup.sh inside the
# tools container.  Never puts secrets in process listings beyond PGPASSFILE path.
set -euo pipefail
export BRAIN_BACKUP_DEST=/tmp/backups
export BRAIN_ASSET_ROOT=/tmp/input/assets
export BRAIN_CONFIG_ROOT=/tmp/input/config
export BRAIN_DELETION_LEDGER=/tmp/input/deletion-ledger.json
export BRAIN_AUTHORITY_MANIFEST=/tmp/input/authoritative-sources.json
export BRAIN_BACKUP_RECIPIENT_FILE=/tmp/input/keys/recipients.age
export BRAIN_BACKUP_FREEZE_HOOK=/tmp/input/freeze-hook.sh
export BRAIN_BACKUP_THAW_HOOK=/tmp/input/thaw-hook.sh
export BRAIN_PG_SERVICE_NAME=brain-pg
export PGSERVICEFILE=/tmp/pgservice.conf
export PGPASSFILE=/tmp/pgpass
export BRAIN_BACKUP_TIER=daily
bash /tmp/backup.sh