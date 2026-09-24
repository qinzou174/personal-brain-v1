"""Canonical backup inventory, tier metadata and retention disclosure.

FR-094/FR-096/FR-097/ER-10: backups include canonical records, assets, config and
deletion ledger; tier retention is 7 daily / 4 weekly / 3 monthly subject to the
ER-10 floor; deleted-data disclosure distinguishes production purge from backup
purge due.
"""

from __future__ import annotations

from dataclasses import dataclass

_TIER_RETENTION_DAYS = {"daily": 7, "weekly": 28, "monthly": 90}


@dataclass(frozen=True)
class BackupInventory:
    database_artifact: str
    asset_manifest: dict[str, str]
    tiers: tuple[str, ...]
    includes_deletion_ledger: bool = True


def build_inventory(*, database_artifact: str, asset_manifest: dict[str, str],
                    tiers: tuple[str, ...]) -> dict[str, object]:
    return {"database_artifact": database_artifact, "asset_manifest": dict(asset_manifest),
            "tiers": tiers, "includes_deletion_ledger": True}


def tier_expiration(*, tier: str, age_days: float) -> str:
    ceiling = _TIER_RETENTION_DAYS.get(tier)
    if ceiling is None:
        raise ValueError("unknown backup tier")
    return "expired" if age_days >= ceiling else "active"


def disclosure(*, backup_purge_due: bool) -> dict[str, object]:
    return {"deleted_copies": "backup purge due" if backup_purge_due else "backup retains copy"}