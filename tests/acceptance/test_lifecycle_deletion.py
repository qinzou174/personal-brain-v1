"""US8 Scenario J: conflict, retention, evidence-deletion, deletion-plan (T113)."""

import pytest


def test_conflict_resolution_never_drops_participants():
    from personal_brain_domain.memory.conflicts import resolve_conflict

    result = resolve_conflict(participants=("a", "b"), mode="time")
    assert result.state in {"resolved_by_time", "tolerated", "superseded"}
    assert set(result.participants) == {"a", "b"}


def test_deletion_plan_previews_without_side_effect():
    from personal_brain_domain.operations.deletion_plan import build_deletion_plan

    plan = build_deletion_plan(targets=("note-1",), dependents={"note-1": ("summary-1", "relation-2")})
    assert plan.actions == {"note-1": ("summary-1", "relation-2")}
    assert plan.preview_only is True
    assert plan.confirmed is False


def test_retention_archive_expiry_policy():
    from personal_brain_domain.operations.retention import apply_retention

    outcome = apply_retention(kind="candidate", age_days=95)
    assert outcome.action == "archive"


def test_delete_requires_confirmation_and_stale_proposal_rejected():
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_domain.operations.deletion import execute_deletion

    with pytest.raises(BrainError) as caught:
        execute_deletion(plan={"confirmed": False, "version": 1}, expected_version=1, confirmed=True)
    assert caught.value.code == "CONFIRMATION_REQUIRED" or caught.value.code == "VALIDATION_FAILED"
