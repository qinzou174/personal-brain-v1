"""Unavailable/failed/pending-sync outcome mapping without false success.

FR-084/FR-087: an offline acknowledgement never claims durable save; it reports
failed or pending_sync honestly.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OfflineOutcome:
    status: str  # failed | pending_sync
    claimed_durable_save: bool = False


def map_offline_outcome(*, unavailable: bool) -> OfflineOutcome:
    if unavailable:
        return OfflineOutcome(status="failed", claimed_durable_save=False)
    return OfflineOutcome(status="pending_sync", claimed_durable_save=False)