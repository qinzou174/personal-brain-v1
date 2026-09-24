"""Replay and deletion tombstone behavior before durable claim wiring."""

import pytest

from personal_brain_domain.common.errors import BrainError
from personal_brain_infra.persistence.idempotency import resolve_replay


def test_same_digest_replays_exact_outcome():
    outcome = {"status": "completed", "record_id": "one"}
    assert resolve_replay("abc", "abc", existing_outcome=outcome) == outcome


def test_different_digest_is_conflict():
    with pytest.raises(BrainError) as caught:
        resolve_replay("abc", "def", existing_outcome={"record_id": "one"})
    assert caught.value.code == "IDEMPOTENCY_CONFLICT"


def test_tombstone_has_no_digest_and_never_recreates():
    assert resolve_replay(None, "any", existing_outcome=None, tombstoned=True) == {
        "status": "deleted", "persistence": "tombstone"
    }
    with pytest.raises(BrainError):
        resolve_replay("must-not-survive-deletion", "any", existing_outcome=None, tombstoned=True)
