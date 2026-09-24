#!/usr/bin/env bash
# Production backup set for the LAN stack: dump + data root + secrets, encrypted.
#
# Everything the stack needs to be brought up on another machine travels in one
# encrypted bundle, and nothing is written into the repository:
#   database.pg_dump  pg_dump -Fc of the live database (client matching the server)
#   data-root.tar.gz  /srv/brain/data (assets + provisioned client material)
#   secrets.tar.gz    the mounted secret files (db_dsn, token_pepper, model key, ...)
#   manifest.json     what was captured, from where, and the checksums
# The passphrase lives beside the secrets; it is generated on first run.
#
# Run on the deployment host:
#   deploy/scripts/prod-backup.sh
# Env overrides: BACKUP_DEST, BACKUP_KEEP, PROJECT_DIR, DATA_DIR,
#                DB_CONTAINER, API_CONTAINER, BACKUP_PASSPHRASE_FILE
#
# Restore outline (see docs/BACKUP_RESTORE.md):
#   openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in <bundle>.age -out bundle.tar \
#     -pass file:<passphrase>
#   tar -xf bundle.tar && docker exec -i <db> pg_restore -U brain -d brain --clean < database.pg_dump
set -euo pipefail
umask 077

PROJECT_DIR="${PROJECT_DIR:-/home/kms/personal-brain-v1-prod}"
DATA_DIR="${DATA_DIR:-/home/kms/personal-brain-v1-prod-data}"
DEST="${BACKUP_DEST:-/home/kms/personal-brain-v1-backups}"
KEEP="${BACKUP_KEEP:-7}"
DB_CONTAINER="${DB_CONTAINER:-personal-brain-v1-prod-db-1}"
API_CONTAINER="${API_CONTAINER:-personal-brain-v1-prod-api-1}"
PASSPHRASE_FILE="${BACKUP_PASSPHRASE_FILE:-$DATA_DIR/secrets/backup_passphrase}"

if [ ! -s "$PASSPHRASE_FILE" ]; then
  mkdir -p "$(dirname "$PASSPHRASE_FILE")"
  openssl rand -base64 48 > "$PASSPHRASE_FILE"
  chmod 600 "$PASSPHRASE_FILE"
  echo "backup_passphrase_created=$PASSPHRASE_FILE"
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$DEST"

# 1) Database, dumped by the server's own client so versions always agree.
docker exec "$DB_CONTAINER" pg_dump -U brain -d brain -Fc > "$STAGE/database.pg_dump"

# 2) Data root (assets, provisioned material) straight from the running volume.
docker exec "$API_CONTAINER" tar -C /srv/brain/data -czf - . > "$STAGE/data-root.tar.gz"

# 3) Mounted secrets, so the stack can be rebuilt on another machine.
tar -C "$DATA_DIR" -czf "$STAGE/secrets.tar.gz" secrets

COVERED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
DB_SIZE="$(stat -c %s "$STAGE/database.pg_dump")"
(cd "$STAGE" && sha256sum database.pg_dump data-root.tar.gz secrets.tar.gz > artifacts.sha256)
cat > "$STAGE/manifest.json" <<EOF
{"format":1,"covered_at":"$COVERED_AT","project":"$(basename "$PROJECT_DIR")","database_bytes":$DB_SIZE,"contents":["database.pg_dump","data-root.tar.gz","secrets.tar.gz"],"encryption":"openssl-aes-256-cbc-pbkdf2","passphrase_file":"$PASSPHRASE_FILE","restore":"docs/BACKUP_RESTORE.md"}
EOF
(cd "$STAGE" && sha256sum manifest.json >> artifacts.sha256)

tar -C "$STAGE" -cf "$STAGE/bundle.tar" \
  database.pg_dump data-root.tar.gz secrets.tar.gz artifacts.sha256 manifest.json

BUNDLE="$DEST/personal-brain-prod-$STAMP.tar.age"
openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
  -in "$STAGE/bundle.tar" -out "$BUNDLE.tmp" -pass file:"$PASSPHRASE_FILE"
test -s "$BUNDLE.tmp"
mv -- "$BUNDLE.tmp" "$BUNDLE"
sha256sum "$BUNDLE" > "$BUNDLE.sha256"

# 4) Retention: keep the newest $KEEP bundles.
mapfile -t OLD < <(find "$DEST" -maxdepth 1 -type f -name 'personal-brain-prod-*.tar.age' \
  -printf '%T@ %p\n' | sort -nr | tail -n "+$((KEEP + 1))" | cut -d' ' -f2-)
for candidate in "${OLD[@]}"; do
  candidate_real="$(realpath "$candidate")"
  case "$candidate_real" in "$DEST"/*) rm -- "$candidate_real" "$candidate_real.sha256" ;;
    *) echo "retention path escaped destination" >&2; exit 4 ;;
  esac
done

echo "backup_created=$BUNDLE bytes=$(stat -c %s "$BUNDLE") covered_at=$COVERED_AT kept=$KEEP"