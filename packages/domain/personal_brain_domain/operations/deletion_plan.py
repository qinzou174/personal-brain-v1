"""Deletion dependency graph and action classification.

FR-079/ER-09: deletion produces a preview-only plan of targets and every
dependent's proposed action; nothing is hidden or purged before confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeletionPlan:
    targets: tuple[object, ...]
    actions: dict[object, tuple[object, ...]]
    preview_only: bool = True
    confirmed: bool = False
    version: int = 1


def build_deletion_plan(*, targets: list[object], dependents: dict[object, tuple[object, ...]]) -> DeletionPlan:
    return DeletionPlan(targets=tuple(targets), actions={t: tuple(dependents.get(t, ())) for t in targets})


def backup_implications(*, backup_tiers: tuple[str, ...], purge_due: bool) -> dict[str, object]:
    """Disclose production_purged separately from backup_purge_due."""
    return {"production_purged": True, "backup_purge_due": purge_due, "backup_tiers": list(backup_tiers)}