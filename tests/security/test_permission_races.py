"""US7 concurrent permission-change and already-running-job safety (T085)."""


def test_permission_change_is_instant_for_new_requests():
    from personal_brain_domain.security.policy import evaluate_permission_epoch

    assert evaluate_permission_epoch(authenticated_epoch=9, current_epoch=9) is True
    assert evaluate_permission_epoch(authenticated_epoch=9, current_epoch=10) is False


def test_running_job_rechecks_permission_before_commit():
    from personal_brain_infra.jobs.store import may_commit_result

    # Permission epoch changed -> worker holding stale token cannot commit result.
    assert not may_commit_result(state="leased", submitted_claim_token=1, current_claim_token=2)
