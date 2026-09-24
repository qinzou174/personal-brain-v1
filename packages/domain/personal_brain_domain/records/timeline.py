"""Event hierarchy, objective/subjective links, Entity types and Relation primitives.

FR-016..FR-019/ER-04: event parents must be acyclic and contained in the owner
boundary; experience is a derived link to one event; relations are typed and can
never cross owner boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


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


@dataclass(frozen=True)
class Experience:
    event_id: object
    user_expression: str
    context: str
    normalized_interpretation: str | None = None
    source_id: object | None = None
    confidence: str | None = None


@dataclass(frozen=True)
class Entity:
    entity_type: str
    canonical_name: str
    aliases: tuple[str, ...] = ()
    source_id: object | None = None
    confidence: str | None = None


@dataclass(frozen=True)
class Relation:
    subject_type: str
    subject_id: object
    predicate: str
    object_type: str
    object_id: object
    source_id: object | None = None
    confidence: str | None = None


def validate_parent_chain(*, event_id: object, parent_id: object, ancestor_ids: list[object]) -> None:
    """A parent may never be (or loop through) the event itself."""
    if parent_id in ancestor_ids or parent_id == event_id:
        raise ValueError("event parent chain must be acyclic")
    if event_id == parent_id:
        raise ValueError("event cannot be its own parent")


def validate_relation_owners(*, subject_owner_id: object, object_owner_id: object) -> None:
    if subject_owner_id != object_owner_id:
        raise ValueError("relations cannot cross owner boundaries")
