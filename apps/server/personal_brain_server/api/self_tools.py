"""Self-model confirmation operations (approve/reject class-C proposals).

FR-026/FR-076/ER-06: only the owner may approve/reject; the proposal is
version-bound and single-use; class-C claims never activate before confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID


@dataclass
class SelfClaim:
    claim_id: str
    category: str
    claim: str
    policy_class: str
    lifecycle: str
    review: str = "none"
    version: int = 1


@dataclass
class _Confirmation:
    claim_id: str
    expected_version: int
    expires_at: datetime
    state: str = "open"


class InMemorySelfTools:
    """Explicit test double; never constructed by the production runtime."""

    def __init__(self) -> None:
        self._claims: dict[str, SelfClaim] = {}
        self._confirmations: dict[str, _Confirmation] = {}

    def propose(self, *, category: str, claim: str, policy_class: str) -> SelfClaim:
        record = SelfClaim(claim_id=f"claim-{len(self._claims) + 1}", category=category, claim=claim,
                           policy_class=policy_class, lifecycle="pending_confirmation" if policy_class == "C" else "candidate")
        self._claims[record.claim_id] = record
        if policy_class == "C":
            self._confirmations[record.claim_id] = _Confirmation(
                claim_id=record.claim_id, expected_version=1,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            )
        return record

    def approve(self, *, claim_id: str, version: int) -> SelfClaim:
        record = self._claims.get(claim_id)
        if record is None:
            raise KeyError("claim not found")
        confirmation = self._confirmations.get(claim_id)
        if confirmation is None:
            raise ValueError("claim requires no confirmation")
        if confirmation.state != "open":
            raise ValueError("confirmation already consumed")
        if datetime.now(timezone.utc) > confirmation.expires_at:
            raise ValueError("confirmation expired")
        if version != confirmation.expected_version:
            raise ValueError("version conflict")
        confirmation.state = "approved"
        record.lifecycle = "active"
        record.review = "none"
        return record

    def reject(self, *, claim_id: str) -> SelfClaim:
        record = self._claims.get(claim_id)
        if record is None:
            raise KeyError("claim not found")
        confirmation = self._confirmations.get(claim_id)
        if confirmation is None:
            raise ValueError("claim requires no confirmation")
        confirmation.state = "rejected"
        record.review = "rejected"
        record.lifecycle = "candidate"
        return record


class SelfTools:
    """Production self-model operations backed by AuthoritativeStore."""

    def __init__(self, repository: object) -> None:
        self._repository = repository

    def propose(
        self, *, category: str, claim: str, policy_class: str,
        requested_scope: str, idempotency_key: UUID,
    ) -> dict:
        return self._repository.propose_self_claim(
            category=category, claim_text=claim, policy_class=policy_class,
            requested_scope=requested_scope, idempotency_key=idempotency_key,
        )
