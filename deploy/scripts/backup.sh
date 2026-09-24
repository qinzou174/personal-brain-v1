#!/usr/bin/env bash
# Fail-closed encrypted, coordinated Personal Brain backup.
set -euo pipefail
umask 077

DEST="${BRAIN_BACKUP_DEST:?required independent backup destination}"
ASSET_ROOT="${BRAIN_ASSET_ROOT:?required asset root}"
CONFIG_ROOT="${BRAIN_CONFIG_ROOT:?required non-secret configuration root}"
DELETION_LEDGER="${BRAIN_DELETION_LEDGER:?required deletion ledger export}"
AUTHORITY_MANIFEST="${BRAIN_AUTHORITY_MANIFEST:?required authoritative-source manifest}"
RECIPIENTS="${BRAIN_BACKUP_RECIPIENT_FILE:?required age recipients file}"
FREEZE_HOOK="${BRAIN_BACKUP_FREEZE_HOOK:?required executable write-freeze hook}"
THAW_HOOK="${BRAIN_BACKUP_THAW_HOOK:?required executable write-thaw hook}"
PG_SERVICE="${BRAIN_PG_SERVICE_NAME:?required pg service name}"
TIER="${BRAIN_BACKUP_TIER:-daily}"
RESERVE_BYTES="${BRAIN_BACKUP_RESERVE_BYTES:-5368709120}"

case "$TIER" in daily|weekly|monthly) ;; *) echo "invalid backup tier" >&2; exit 2 ;; esac
for command in pg_dump pg_restore age sha256sum tar find sort realpath df du awk tail tr xargs cut mktemp date cp mv rm; do
  command -v "$command" >/dev/null 2>&1 || { echo "missing required command: $command" >&2; exit 2; }
done
for directory in "$DEST" "$ASSET_ROOT" "$CONFIG_ROOT"; do
  test -d "$directory" || { echo "required directory unavailable" >&2; exit 2; }
done
for file in "$DELETION_LEDGER" "$AUTHORITY_MANIFEST" "$RECIPIENTS"; do
  test -s "$file" || { echo "required manifest/recipient file unavailable" >&2; exit 2; }
done
test -x "$FREEZE_HOOK" && test -x "$THAW_HOOK" || { echo "backup coordination hooks are not executable" >&2; exit 2; }
test -n "${PGSERVICEFILE:-}" && test -r "$PGSERVICEFILE" || { echo "PGSERVICEFILE is required" >&2; exit 2; }
test -n "${PGPASSFILE:-}" && test -r "$PGPASSFILE" || { echo "PGPASSFILE is required" >&2; exit 2; }

DEST_REAL="$(realpath "$DEST")"
TIER_DIR="$DEST_REAL/$TIER"
mkdir -p "$TIER_DIR"
STAGE="$(mktemp -d "$DEST_REAL/.brain-backup.XXXXXX")"
FROZEN=0
cleanup() {
  if test "$FROZEN" -eq 1; then "$THAW_HOOK"; fi
  rm -rf -- "$STAGE"
}
trap cleanup EXIT INT TERM

SOURCE_BYTES="$(du -sb "$ASSET_ROOT" "$CONFIG_ROOT" | awk '{total += $1} END {print total + 0}')"
AVAILABLE_BYTES="$(df --output=avail -B1 "$DEST_REAL" | tail -n 1 | tr -d ' ')"
REQUIRED_BYTES="$((SOURCE_BYTES * 3 + RESERVE_BYTES))"
test "$AVAILABLE_BYTES" -ge "$REQUIRED_BYTES" || { echo "insufficient backup capacity" >&2; exit 3; }

"$FREEZE_HOOK"
FROZEN=1
CUTOFF="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
pg_dump --dbname="service=$PG_SERVICE" --format=custom --file="$STAGE/database.pg_dump"
tar -C "$ASSET_ROOT" -cf "$STAGE/assets.tar" .
tar -C "$CONFIG_ROOT" -cf "$STAGE/configuration.tar" .
cp -- "$DELETION_LEDGER" "$STAGE/deletion-ledger.json"
cp -- "$AUTHORITY_MANIFEST" "$STAGE/authoritative-sources.json"
"$THAW_HOOK"
FROZEN=0

sha256sum "$STAGE/database.pg_dump" "$STAGE/assets.tar" "$STAGE/configuration.tar" \
  "$STAGE/deletion-ledger.json" "$STAGE/authoritative-sources.json" > "$STAGE/artifacts.sha256"
find "$ASSET_ROOT" -type f -print0 | sort -z | xargs -0 -r sha256sum > "$STAGE/assets.sha256"
MIGRATION_VERSION="$(pg_restore --list "$STAGE/database.pg_dump" | sha256sum | awk '{print $1}')"
cat > "$STAGE/manifest.json" <<EOF
{"format":1,"covered_at":"$CUTOFF","tier":"$TIER","database_artifact":"database.pg_dump","asset_manifest":"assets.sha256","configuration_artifact":"configuration.tar","deletion_ledger":"deletion-ledger.json","authoritative_sources":"authoritative-sources.json","schema_inventory_sha256":"$MIGRATION_VERSION","encryption":"age","state":"complete"}
EOF
sha256sum "$STAGE/manifest.json" >> "$STAGE/artifacts.sha256"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BUNDLE="$STAGE/personal-brain-$STAMP-$TIER.tar"
tar -C "$STAGE" -cf "$BUNDLE" database.pg_dump assets.tar configuration.tar \
  deletion-ledger.json authoritative-sources.json assets.sha256 artifacts.sha256 manifest.json
FINAL="$TIER_DIR/personal-brain-$STAMP-$TIER.tar.age"
age --encrypt --recipients-file "$RECIPIENTS" --output "$FINAL.tmp" "$BUNDLE"
test -s "$FINAL.tmp"
mv -- "$FINAL.tmp" "$FINAL"
sha256sum "$FINAL" > "$FINAL.sha256"

case "$TIER" in daily) KEEP=7 ;; weekly) KEEP=4 ;; monthly) KEEP=3 ;; esac
mapfile -t OLD < <(find "$TIER_DIR" -maxdepth 1 -type f -name 'personal-brain-*.tar.age' -printf '%T@ %p\n' | sort -nr | tail -n "+$((KEEP + 1))" | cut -d' ' -f2-)
for candidate in "${OLD[@]}"; do
  CANDIDATE_REAL="$(realpath "$candidate")"
  case "$CANDIDATE_REAL" in "$TIER_DIR"/*) rm -- "$CANDIDATE_REAL" "$CANDIDATE_REAL.sha256" ;; *) echo "retention path escaped destination" >&2; exit 4 ;; esac
done

echo "backup_set_created=$FINAL covered_at=$CUTOFF tier=$TIER"
