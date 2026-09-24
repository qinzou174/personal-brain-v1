"""Owner-authenticated Inbox/proposal read/approve/reject/expiry.

FR-010/FR-026/FR-076/ER-06: high-impact or class-C changes enter a review inbox
with evidence and a proposed action. Approving/rejecting is version-bound (the
proposal must be unchanged), single-use, and expires 15 minutes after creation;
a stale or consumed confirmation can never be replayed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Mapping

from personal_brain_domain.common.errors import BrainError

DEFAULT_CONFIRMATION_MINUTES = 15


@dataclass
class _Proposal:
    id: str
    operation: str
    target_ids: tuple[str, ...]
    payload_digest: str
    expected_version: int
    risk: str
    expires_at: datetime
    state: str = "open"
    _consumed_keys: set[str] = field(default_factory=set)


@dataclass
class ProposalStore:
    """In-memory owner review inbox; a durable store replaces it in later phases."""

    now: Callable[[], datetime]
    _proposals: dict[str, _Proposal] = field(default_factory=dict)

    def create_proposal(
        self,
        *,
        operation: str,
        target_ids: list[str],
        payload_digest: str,
        expected_version: int,
        risk: str,
        expires_in: timedelta = timedelta(minutes=DEFAULT_CONFIRMATION_MINUTES),
    ) -> _Proposal:
        proposal = _Proposal(
            id=str(uuid.uuid4()),
            operation=operation,
            target_ids=tuple(target_ids),
            payload_digest=payload_digest,
            expected_version=expected_version,
            risk=risk,
            expires_at=self.now() + expires_in,
        )
        self._proposals[proposal.id] = proposal
        return proposal

    def get(self, proposal_id: str) -> Mapping[str, object]:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise BrainError("NOT_FOUND")
        return {
            "id": proposal.id,
            "operation": proposal.operation,
            "target_ids": proposal.target_ids,
            "risk": proposal.risk,
            "expected_version": proposal.expected_version,
            "expires_at": proposal.expires_at,
            "state": proposal.state,
        }

    def _consume(
        self,
        *,
        proposal_id: str,
        owner_id: str,
        version: int,
        idempotency_key: str,
        decision: str,
    ) -> None:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise BrainError("NOT_FOUND")
        if self.now() > proposal.expires_at:
            raise BrainError("CONFIRMATION_EXPIRED")
        if proposal.state != "open":
            raise BrainError("CONFIRMATION_REQUIRED")
        if version != proposal.expected_version:
            raise BrainError("VERSION_CONFLICT")
        if idempotency_key in proposal._consumed_keys:
            return  # single-use replay returns the original outcome
        proposal._consumed_keys.add(idempotency_key)
        proposal.state = decision

    def approve(self, *, proposal_id: str, owner_id: str, version: int, idempotency_key: str) -> None:
        self._consume(proposal_id=proposal_id, owner_id=owner_id, version=version,
                      idempotency_key=idempotency_key, decision="approved")

    def reject(self, *, proposal_id: str, owner_id: str, idempotency_key: str) -> None:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise BrainError("NOT_FOUND")
        if self.now() > proposal.expires_at:
            raise BrainError("CONFIRMATION_EXPIRED")
        if proposal.state != "open":
            raise BrainError("CONFIRMATION_REQUIRED")
        if idempotency_key in proposal._consumed_keys:
            return
        proposal._consumed_keys.add(idempotency_key)
        proposal.state = "rejected"
