"""Type-specific retention, archive, expiry, promotion and demotion orchestration.

FR-021/FR-022/FR-081/FR-082: retention is policy-specific to information class;
candidates older than the expiry window archive, established memories move to
historical, never a single age rule for all memories.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetentionOutcome:
    action: str  # active | archive | historical | expire | delete


def apply_retention(*, kind: str, age_days: float) -> RetentionOutcome:
    if kind == "candidate":
        return RetentionOutcome(action="archive" if age_days > 90 else "active")
    if kind == "established":
        return RetentionOutcome(action="historical" if age_days > 180 else "active")
    if kind == "temporary":
        return RetentionOutcome(action="expire" if age_days > 30 else "active")
    return RetentionOutcome(action="active")