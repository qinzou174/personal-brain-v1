#!/usr/bin/env bash
# Prepare T183 backup inputs: assets, config, ledger, manifests, hooks, recipients.
set -euo pipefail
umask 077

ROOT="${1:?input root}"
ASSETS="$ROOT/assets"
CONFIG="$ROOT/config"
mkdir -p "$ASSETS" "$CONFIG" "$ROOT/keys"

# A small but real asset + config corpus for the backup set.
printf 'personal brain asset one\n' > "$ASSETS/note-one.txt"
printf 'personal brain asset two\n' > "$ASSETS/note-two.txt"
printf '{"site_language":"zh-CN"}\n' > "$CONFIG/site.json"
printf '{"timezone":"Asia/Shanghai"}\n' > "$CONFIG/settings.json"

# Deployment ledger and authoritative-source manifest (non-secret).
cat > "$ROOT/deletion-ledger.json" <<'EOF'
{"entries":[]}
EOF
cat > "$ROOT/authoritative-sources.json" <<'EOF'
{"owners":true,"clients":true,"expenses":true,"todos":true,"projects":true,"assets":true,"search_index_entries":true,"deletion_ledger":true}
EOF

# Freeze/thaw hooks: a stamp file guards coordinated DB/asset cutoff.
cat > "$ROOT/freeze-hook.sh" <<'EOF'
#!/usr/bin/env bash
set -e
mkdir -p /home/kms/personal-brain-v1-backup-input/.fence
echo frozen > /home/kms/personal-brain-v1-backup-input/.fence/state
EOF
cat > "$ROOT/thaw-hook.sh" <<'EOF'
#!/usr/bin/env bash
set -e
rm -rf /home/kms/personal-brain-v1-backup-input/.fence
EOF
chmod 700 "$ROOT/freeze-hook.sh" "$ROOT/thaw-hook.sh"

# Recipients file: the age public key is the only thing we hand to the backup script.
recipient="$(docker exec brain-backup-tools bash -c 'age-keygen -y /tmp/brain-backup-identity.txt')"
printf '%s\n' "$recipient" > "$ROOT/keys/recipients.age"
echo "recipient=$recipient"
echo "prepared"