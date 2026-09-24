"""Review inbox operations for conflict, merge, profile, deletion and reconciliation.

FR-010/FR-026/FR-077..FR-080: owner reviews proposals; approving consumes the
proposal once, rejecting leaves participants intact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from personal_brain_domain.common.errors import BrainError


@dataclass
class ReviewItem:
    item_id: str
    item_type: str
    subject_refs: tuple[object, ...]
    state: str = "open"


@dataclass
class InMemoryReviewInbox:
    """Explicit test double; production uses the repository-bound ReviewInbox."""

    items: dict[str, ReviewItem] = field(default_factory=dict)

    def add(self, *, item_type: str, subject_refs: tuple[object, ...]) -> str:
        item = ReviewItem(item_id=f"item-{len(self.items) + 1}", item_type=item_type, subject_refs=subject_refs)
        self.items[item.item_id] = item
        return item.item_id

    def approve(self, item_id: str) -> ReviewItem:
        item = self.items.get(item_id)
        if item is None:
            raise BrainError("NOT_FOUND")
        if item.state != "open":
            raise BrainError("CONFIRMATION_REQUIRED")
        item.state = "approved"
        return item

    def reject(self, item_id: str) -> ReviewItem:
        item = self.items.get(item_id)
        if item is None:
            raise BrainError("NOT_FOUND")
        if item.state != "open":
            raise BrainError("CONFIRMATION_REQUIRED")
        item.state = "rejected"
        return item


class ReviewInbox:
    def __init__(self, repository: object) -> None:
        self._repository = repository

    def add(
        self, *, item_type: str, subject_refs: list[str], proposal: dict,
        requested_scope: str, idempotency_key: UUID,
    ) -> dict:
        return self._repository.create_review_item(
            item_type=item_type, subject_refs=subject_refs, proposal=proposal,
            requested_scope=requested_scope, idempotency_key=idempotency_key,
        )
