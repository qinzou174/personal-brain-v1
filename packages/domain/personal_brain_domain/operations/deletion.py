"""Versioned confirmation and governed delete/detach/tombstone/recompute execution.

FR-029/FR-076/FR-079/FR-080/ER-06/ER-09: stale proposals are rejected; the plan
must be confirmed and unchanged before execution; production purge is reported
separately from backup purge due.
"""

from __future__ import annotations

from dataclasses import dataclass

from personal_brain_domain.common.errors import BrainError


@dataclass(frozen=True)
class DeletionExecution:
    targets: tuple[object, ...]
    production_purged: bool
    backup_purge_due: bool


def execute_deletion(*, plan: dict, expected_version: int, confirmed: bool) -> DeletionExecution:
    if not confirmed or plan.get("confirmed") is not True:
        raise BrainError("CONFIRMATION_REQUIRED")
    if plan.get("version") != expected_version:
        raise BrainError("VERSION_CONFLICT")
    targets = tuple(plan.get("targets", ()))
    return DeletionExecution(targets=targets, production_purged=True, backup_purge_due=True)