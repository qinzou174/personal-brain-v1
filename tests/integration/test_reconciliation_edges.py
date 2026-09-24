"""US9 revoked-client-with-pending-writes and crash-after-commit edges (T124)."""


def test_revoked_client_stops_replay():
    from personal_brain_bridge.pending_store import pending_write_state

    assert pending_write_state(revoked=True, queued=True) == "stopped"


def test_crash_after_commit_produces_single_outcome_on_retry():
    from personal_brain_bridge.reconcile import reconcile_once

    outcome = reconcile_once(operation_id="op-9", attempts=("done",))
    assert outcome == ("done",)
