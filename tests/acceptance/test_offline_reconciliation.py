"""US9 Scenario I: offline acknowledgement, replay, conflict (T123)."""

import pytest


def test_offline_mutation_reports_honest_status():
    from personal_brain_bridge.offline import map_offline_outcome

    outcome = map_offline_outcome(unavailable=True)
    assert outcome.status in {"failed", "pending_sync"}
    assert outcome.claimed_durable_save is False


def test_replay_reconciles_to_one_authoritative_outcome():
    from personal_brain_bridge.reconcile import reconcile_once

    result = reconcile_once(operation_id="op-1", attempts=("outcome-x", "outcome-x", "outcome-x"))
    assert len(set(result)) == 1


def test_conflicting_version_enters_review_without_loss():
    from personal_brain_domain.intake.reconciliation import handoff_conflict_to_review

    result = handoff_conflict_to_review(version_a="v1", version_b="v2")
    assert set(result.participants) == {"v1", "v2"}
    assert result.review_item_type == "conflict"
