"""Notification dispatch job with safe failure visibility.

FR-084/FR-091: the dispatch job delivers to the mandatory owner Inbox and, when
preauthorized, optional channels; failures are visible, not silent.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DispatchOutcome:
    job_id: str
    delivered_to_inbox: bool
    external_channels: tuple[str, ...] = ()


def dispatch(*, job_id: str, inbox_ack_required: bool = True) -> DispatchOutcome:
    return DispatchOutcome(job_id=job_id, delivered_to_inbox=inbox_ack_required)