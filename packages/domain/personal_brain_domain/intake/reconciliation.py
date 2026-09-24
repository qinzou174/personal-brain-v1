"""Conflict-to-review handoff preserving both versions.

FR-010/FR-077/FR-088: when offline replay produces conflicting versions, both
enter the review inbox with their evidence; neither is silently lost.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewHandoff:
    review_item_type: str
    participants: tuple[object, ...]
    state: str = "open"


def handoff_conflict_to_review(*, version_a: object, version_b: object) -> ReviewHandoff:
    return ReviewHandoff(review_item_type="conflict", participants=(version_a, version_b))