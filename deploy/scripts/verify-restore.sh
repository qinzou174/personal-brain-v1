#!/usr/bin/env bash
# Isolated restore verification from independent expected/restored manifests.
set -euo pipefail
EXPECTED_MANIFEST="${BRAIN_EXPECTED_RESTORE_MANIFEST:?required}"
RESTORED_MANIFEST="${BRAIN_RESTORED_EVIDENCE_MANIFEST:?required}"
OUTPUT="${BRAIN_RESTORE_VERIFICATION_OUTPUT:?required}"
test "$EXPECTED_MANIFEST" != "$RESTORED_MANIFEST"
python -m personal_brain_domain.operations.restore_cli \
  --expected "$EXPECTED_MANIFEST" \
  --restored "$RESTORED_MANIFEST" \
  --output "$OUTPUT"
grep -q '"verified": true' "$OUTPUT"
echo "restore_verified=yes evidence=$OUTPUT"
