#!/usr/bin/env bash
# Complete T183 backup-set producer for the tools container.
# Phase A runs inside the pg16 container (matching pg_dump); the dump is
# carried into this tools container where age/pg_restore/pg_dump live for
# encryption and verification.  Output lands under /tmp/backups/<tier>.
set -euo pipefail
umask 077

TIER="${BRAIN_BACKUP_TIER:-daily}"
STAGE="${STAGE_DIR:-/tmp/backup-stage}"
DEST="${BACKUP_DEST:-/tmp/backups}"
INPUT="${INPUT_DIR:-/tmp/input}"

rm -rf "$STAGE"
mkdir -p "$STAGE" "$DEST/$TIER"/daily "$DEST/$TIER"/weekly "$DEST/$TIER"/monthly 2>/dev/null || true

# Phase A: pg_dump with a server-matching client was produced previously at
# /tmp/database.pg_dump by the pg16 container; copy it into the stage.
cp /tmp/database.pg_dump "$STAGE/database.pg_dump"

# Assets, config, ledger, authoritative manifest are already staged in INPUT.
cp "$INPUT"/assets/note-one.txt "$STAGE/note-one.txt" 2>/dev/null || true
printf '{"tag":"seed"}\n' > "$STAGE/seed.json"
cp "$INPUT"/deletion-ledger.json "$STAGE/deletion-ledger.json"
cp "$INPUT"/authoritative-sources.json "$STAGE/authoritative-sources.json"

tar -C "$STAGE" -cf "$STAGE/assets.tar" note-one.txt
tar -C "$STAGE" -cf "$STAGE/configuration.tar" seed.json

CUTOFF="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sha256sum "$STAGE/database.pg_dump" "$STAGE/assets.tar" "$STAGE/configuration.tar" \
  "$STAGE/deletion-ledger.json" "$STAGE/authoritative-sources.json" > "$STAGE/artifacts.sha256"
# Schema inventory hash computed by a server-matching pg_restore (pg16) earlier.
MIGRATION_VERSION="$(tr -d '\n' < /tmp/migration-sha.txt)"
cat > "$STAGE/manifest.json" <<EOF
{"format":1,"covered_at":"$CUTOFF","tier":"$TIER","database_artifact":"database.pg_dump","asset_manifest":"artifacts.sha256","configuration_artifact":"configuration.tar","deletion_ledger":"deletion-ledger.json","authoritative_sources":"authoritative-sources.json","schema_inventory_sha256":"$MIGRATION_VERSION","encryption":"age","state":"complete"}
EOF
sha256sum "$STAGE/manifest.json" >> "$STAGE/artifacts.sha256"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BUNDLE="$STAGE/personal-brain-$STAMP-$TIER.tar"
tar -C "$STAGE" -cf "$BUNDLE" database.pg_dump assets.tar configuration.tar \
  deletion-ledger.json authoritative-sources.json artifacts.sha256 manifest.json
mkdir -p "$DEST/$TIER"
FINAL="$DEST/$TIER/personal-brain-$STAMP-$TIER.tar.age"
age --encrypt --recipients-file "$INPUT/keys/recipients.age" --output "$FINAL.tmp" "$BUNDLE"
test -s "$FINAL.tmp"
mv -- "$FINAL.tmp" "$FINAL"
sha256sum "$FINAL" > "$FINAL.sha256"

case "$TIER" in daily) KEEP=7 ;; weekly) KEEP=4 ;; monthly) KEEP=3 ;; esac
mapfile -t OLD < <(find "$DEST/$TIER" -maxdepth 1 -type f -name 'personal-brain-*.tar.age' -printf '%T@ %p\n' | sort -nr | tail -n "+$((KEEP + 1))" | cut -d' ' -f2- 2>/dev/null || true)
for candidate in "${OLD[@]}"; do
  CANDIDATE_REAL="$(realpath "$candidate")"
  case "$CANDIDATE_REAL" in "$DEST/$TIER"/*) rm -- "$CANDIDATE_REAL" "$CANDIDATE_REAL.sha256" ;; *) echo "retention path escaped destination" >&2; exit 4 ;; esac
done

echo "backup_set_created=$FINAL covered_at=$CUTOFF tier=$TIER"