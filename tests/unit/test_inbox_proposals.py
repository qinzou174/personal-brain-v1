"""Owner-authenticated Inbox proposal lifecycle (T037, FR-010/026/076, ER-06)."""

from datetime import datetime, timedelta, timezone

import pytest


def _now():
    return datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)


def test_proposal_read_approve_reject_flow():
    from personal_brain_server.api.inbox import ProposalStore

    store = ProposalStore(now=_now)
    proposal = store.create_proposal(
        operation="activate_self_claim", target_ids=["claim-1"], payload_digest="digest",
        expected_version=3, risk="high", expires_in=timedelta(minutes=15),
    )
    assert store.get(proposal.id)["risk"] == "high"
    store.approve(proposal_id=proposal.id, owner_id="owner-1", version=3, idempotency_key="k-approve")
    assert store.get(proposal.id)["state"] == "approved"
    with pytest.raises(Exception):
        store.approve(proposal_id=proposal.id, owner_id="owner-1", version=3, idempotency_key="k-2")


def test_proposal_reject_and_expiry():
    from personal_brain_server.api.inbox import ProposalStore

    store = ProposalStore(now=_now)
    proposal = store.create_proposal(
        operation="delete_asset", target_ids=["a-1"], payload_digest="d",
        expected_version=1, risk="high", expires_in=timedelta(minutes=15),
    )
    store.reject(proposal_id=proposal.id, owner_id="owner-1", idempotency_key="k-reject")
    assert store.get(proposal.id)["state"] == "rejected"
    current = {"at": _now()}
    clock_store = ProposalStore(now=lambda: current["at"])
    expired = clock_store.create_proposal(
        operation="broaden_grant", target_ids=[], payload_digest="d",
        expected_version=1, risk="high", expires_in=timedelta(minutes=15),
    )
    current["at"] = _now() + timedelta(minutes=16)
    with pytest.raises(Exception) as caught:
        clock_store.approve(proposal_id=expired.id, owner_id="owner-1", version=1, idempotency_key="k-expired")
    assert caught.value.code == "CONFIRMATION_EXPIRED"
