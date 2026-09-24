"""Typed relation primitives.

FR-019/ER-04: relations are typed links between records, events, entities,
evidence, project objects and assets; both endpoints must exist and can never
cross owner boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Relation:
    subject_type: str
    subject_id: object
    predicate: str
    object_type: str
    object_id: object
    source_id: object | None = None
    confidence: str | None = None
    lifecycle_state: str = "active"


def validate_relation_owners(*, subject_owner_id: object, object_owner_id: object) -> None:
    if subject_owner_id != object_owner_id:
        raise ValueError("relations cannot cross owner boundaries")
