"""V1 trigger registry and detect-notify separation.

FR-089/FR-090: notifications are limited to explicit triggers (todo deadlines,
sync/index failure, backup/storage failure, Brain health failure); detection and
notification are separate so a detected-but-not-notified case stays possible.
"""

from __future__ import annotations

from dataclasses import dataclass

_TRIGGERS = frozenset({
    "todo_deadline", "sync_index_failure", "backup_storage_failure", "brain_health_failure", "preference_trend",
    "review_item_pending",
})
_NOTIFYING_TRIGGERS = frozenset({"todo_deadline", "sync_index_failure", "backup_storage_failure", "brain_health_failure", "review_item_pending"})


@dataclass(frozen=True)
class TriggerEvaluation:
    trigger_type: str
    notify: bool
    priority: str = "normal"


def evaluate_trigger(*, trigger_type: str, risk: str) -> TriggerEvaluation:
    if trigger_type not in _TRIGGERS:
        raise ValueError("unknown trigger type")
    if trigger_type == "preference_trend":
        return TriggerEvaluation(trigger_type=trigger_type, notify=False)  # detected, not notified by default
    priority = "high" if risk in {"high", "critical"} else "normal"
    return TriggerEvaluation(trigger_type=trigger_type, notify=trigger_type in _NOTIFYING_TRIGGERS, priority=priority)