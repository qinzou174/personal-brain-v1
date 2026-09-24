"""CLI for comparing independent expected and restored evidence manifests."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from personal_brain_domain.operations.restore import verify_restore


def _read(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError("restore manifest must be an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--restored", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    expected, restored = _read(args.expected), _read(args.restored)
    result = verify_restore(
        expected_counts=expected["counts"], restored_counts=restored["counts"],
        relationship_checks=restored["relationship_checks"],
        permission_cases=restored["permission_cases"],
        representative_queries=restored["representative_queries"],
        expected_deletion_ledger_hash=expected["deletion_ledger_hash"],
        restored_deletion_ledger_hash=restored["deletion_ledger_hash"],
        expected_asset_hashes=expected["asset_hashes"], restored_asset_hashes=restored["asset_hashes"],
        backup_completed_at=datetime.fromisoformat(expected["backup_completed_at"]),
        restore_verified_at=datetime.fromisoformat(restored["restore_verified_at"]),
    )
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
