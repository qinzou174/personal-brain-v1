"""Fail-closed encrypted backup contract for T183."""

from pathlib import Path


def test_backup_requires_independent_destination_encryption_cutoff_and_manifests():
    script = Path("deploy/scripts/backup.sh").read_text(encoding="utf-8")
    assert "set -euo pipefail" in script and "|| true" not in script
    for required in (
        "BRAIN_BACKUP_DEST", "BRAIN_ASSET_ROOT", "BRAIN_CONFIG_ROOT",
        "BRAIN_DELETION_LEDGER", "BRAIN_AUTHORITY_MANIFEST",
        "BRAIN_BACKUP_RECIPIENT_FILE", "BRAIN_BACKUP_FREEZE_HOOK",
        "BRAIN_BACKUP_THAW_HOOK", "PGSERVICEFILE", "PGPASSFILE",
    ):
        assert required in script
    assert "age --encrypt --recipients-file" in script
    assert "pg_dump --dbname=\"service=$PG_SERVICE\" --format=custom" in script
    assert "insufficient backup capacity" in script
    assert 'case "$TIER" in daily|weekly|monthly)' in script
    assert "artifacts.sha256" in script and "assets.sha256" in script


def test_backup_retention_never_targets_outside_resolved_tier_directory():
    script = Path("deploy/scripts/backup.sh").read_text(encoding="utf-8")
    assert 'case "$CANDIDATE_REAL" in "$TIER_DIR"/*)' in script
    assert "KEEP=7" in script and "KEEP=4" in script and "KEEP=3" in script
