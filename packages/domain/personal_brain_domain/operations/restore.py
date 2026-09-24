"""Fail-closed isolated restore evidence evaluation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("restore timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def verify_restore(
    *,
    expected_counts: Mapping[str, int],
    restored_counts: Mapping[str, int],
    relationship_checks: Mapping[str, bool],
    permission_cases: Mapping[str, bool],
    representative_queries: Mapping[str, bool],
    expected_deletion_ledger_hash: str,
    restored_deletion_ledger_hash: str,
    expected_asset_hashes: Mapping[str, str],
    restored_asset_hashes: Mapping[str, str],
    backup_completed_at: datetime,
    restore_verified_at: datetime,
) -> dict[str, object]:
    """Verify exact restore evidence; missing evidence is always a failure."""
    if any(not isinstance(value, int) or value < 0 for value in (*expected_counts.values(), *restored_counts.values())):
        raise ValueError("record counts must be non-negative integers")
    failures: list[str] = []
    expected_total = sum(expected_counts.values())
    matched_total = 0
    for name, expected in expected_counts.items():
        restored = restored_counts.get(name)
        if restored != expected:
            failures.append(f"count:{name}")
        if restored is not None:
            matched_total += min(expected, restored)
    for name in set(restored_counts).difference(expected_counts):
        failures.append(f"unexpected_count:{name}")
    fixture_percent = 100.0 if expected_total == 0 and not failures else (
        0.0 if expected_total == 0 else round(matched_total / expected_total * 100, 4)
    )
    for prefix, checks in (
        ("relationship", relationship_checks),
        ("permission", permission_cases),
        ("query", representative_queries),
    ):
        if not checks:
            failures.append(f"{prefix}:missing")
        failures.extend(f"{prefix}:{name}" for name, passed in checks.items() if passed is not True)
    ledger_match = bool(expected_deletion_ledger_hash) and expected_deletion_ledger_hash == restored_deletion_ledger_hash
    if not ledger_match:
        failures.append("deletion_ledger")
    assets_match = bool(expected_asset_hashes) and dict(expected_asset_hashes) == dict(restored_asset_hashes)
    if not assets_match:
        failures.append("asset_hashes")
    independent_timestamps = _utc(restore_verified_at) > _utc(backup_completed_at)
    if not independent_timestamps:
        failures.append("independent_timestamps")
    return {
        "fixture_percent": fixture_percent,
        "verified": not failures and fixture_percent == 100.0,
        "expected_counts": dict(expected_counts), "restored_counts": dict(restored_counts),
        "relationship_checks": dict(relationship_checks), "permission_cases": dict(permission_cases),
        "representative_queries": dict(representative_queries), "deletion_ledger_match": ledger_match,
        "asset_hashes_total": len(expected_asset_hashes),
        "asset_hashes_matched": sum(restored_asset_hashes.get(name) == digest for name, digest in expected_asset_hashes.items()),
        "backup_completed_at": _utc(backup_completed_at).isoformat(),
        "restore_verified_at": _utc(restore_verified_at).isoformat(), "failures": failures,
    }
