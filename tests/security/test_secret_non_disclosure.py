"""US7 permission races and secret non-disclosure (T085/T086)."""

import pytest


def test_permission_change_blocks_new_requests_immediately():
    from personal_brain_domain.security.policy import evaluate_permission_epoch

    assert evaluate_permission_epoch(authenticated_epoch=7, current_epoch=8) is False
    assert evaluate_permission_epoch(authenticated_epoch=8, current_epoch=8) is True


def test_no_secret_in_log_search_or_audit():
    from personal_brain_domain.common.errors import safe_error
    from personal_brain_domain.security.audit import audit_repr, build_audit_event

    marker = "sk-live-never-logged"
    response = safe_error(ValueError(marker), code="SECRET_REJECTED")
    assert marker not in repr(response)
    event = build_audit_event(client_id="c", action="upload", outcome="denied", duration_ms=1,
                              correlation_id="corr", details={"path": "/tmp", "body": marker})
    assert marker not in audit_repr(event)
