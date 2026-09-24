"""Event primitives: hierarchy, temporal bounds and objective/subjective links.

FR-016/FR-017/ER-04: parent/child chains must be acyclic; an experience is linked
to exactly one event and is never a standalone global fact.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    event_id: object
    event_type: str
    title: str
    objective_description: str
    importance: str
    event_timezone: str
    start_at: object | None = None
    end_at: object | None = None
    subjective_experience_id: object | None = None
    parent_event_id: object | None = None
    confidence: str | None = None
    source_id: object | None = None
    lifecycle_state: str = "active"


def validate_parent_chain(*, event_id: object, parent_id: object, ancestor_ids: list[object]) -> None:
    """A parent may never be (or loop through) the event itself."""
    if event_id == parent_id or event_id in ancestor_ids or parent_id in ancestor_ids:
        raise ValueError("event parent chain must be acyclic")


def validate_event_temporal_order(*, start_at, end_at) -> None:
    if end_at is not None and start_at is not None and end_at < start_at:
        raise ValueError("event end precedes start")
