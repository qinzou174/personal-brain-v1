"""US10 Scenario L: backup inventory and isolated restore (T138/T140)."""

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone


def test_backup_inventory_lists_tiers_and_hashes():
    from personal_brain_domain.operations.backup import build_inventory

    inventory = build_inventory(database_artifact="db.bak", asset_manifest={"a1": hashlib.sha256(b"x").hexdigest()},
                                tiers=("daily", "weekly", "monthly"))
    assert inventory["database_artifact"] == "db.bak"
    assert inventory["tiers"] == ("daily", "weekly", "monthly")


def test_backup_retention_discloses_deleted_data():
    from personal_brain_domain.operations.backup import tier_expiration

    assert tier_expiration(tier="daily", age_days=7) == "expired"
    assert tier_expiration(tier="weekly", age_days=28) == "expired"
    assert tier_expiration(tier="monthly", age_days=60) == "active"


def test_restore_verification_records_results_not_passed_by_default():
    from personal_brain_domain.operations.restore import verify_restore

    backup_at = datetime.now(timezone.utc)
    result = verify_restore(
        expected_counts={"note": 100, "todo": 2}, restored_counts={"note": 100, "todo": 1},
        relationship_checks={"source_links": True}, permission_cases={"revoked_denied": True},
        representative_queries={"expense_total": True},
        expected_deletion_ledger_hash="ledger", restored_deletion_ledger_hash="ledger",
        expected_asset_hashes={"a": "hash"}, restored_asset_hashes={"a": "hash"},
        backup_completed_at=backup_at, restore_verified_at=backup_at + timedelta(minutes=1),
    )
    assert result["fixture_percent"] < 100
    assert result["verified"] is False
    assert "count:todo" in result["failures"]


def test_restore_verification_passes_only_for_exact_independent_evidence():
    from personal_brain_domain.operations.restore import verify_restore

    backup_at = datetime.now(timezone.utc)
    result = verify_restore(
        expected_counts={"note": 100}, restored_counts={"note": 100},
        relationship_checks={"source_links": True}, permission_cases={"revoked_denied": True},
        representative_queries={"expense_total": True},
        expected_deletion_ledger_hash="ledger", restored_deletion_ledger_hash="ledger",
        expected_asset_hashes={"a": "hash"}, restored_asset_hashes={"a": "hash"},
        backup_completed_at=backup_at, restore_verified_at=backup_at + timedelta(minutes=1),
    )
    assert result["fixture_percent"] == 100
    assert result["verified"] is True


def test_restore_cli_exits_nonzero_and_records_failures(tmp_path):
    backup_at = datetime.now(timezone.utc)
    expected = tmp_path / "expected.json"
    restored = tmp_path / "restored.json"
    output = tmp_path / "result.json"
    expected.write_text(json.dumps({
        "counts": {"note": 2}, "deletion_ledger_hash": "one",
        "asset_hashes": {"a": "hash"}, "backup_completed_at": backup_at.isoformat(),
    }), encoding="utf-8")
    restored.write_text(json.dumps({
        "counts": {"note": 1}, "relationship_checks": {"links": True},
        "permission_cases": {"denied": True}, "representative_queries": {"query": True},
        "deletion_ledger_hash": "one", "asset_hashes": {"a": "hash"},
        "restore_verified_at": (backup_at + timedelta(minutes=1)).isoformat(),
    }), encoding="utf-8")
    completed = subprocess.run([
        sys.executable, "-m", "personal_brain_domain.operations.restore_cli",
        "--expected", str(expected), "--restored", str(restored), "--output", str(output),
    ], check=False)
    assert completed.returncode == 1
    assert json.loads(output.read_text(encoding="utf-8"))["verified"] is False
