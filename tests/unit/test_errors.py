from personal_brain_domain.common.errors import BrainError, STABLE_CODES, safe_error


def test_stable_error_codes_have_safe_mappings():
    # Protocol-level transport refusals are part of the stable surface: they must
    # stay distinguishable from credential failures on the wire.
    assert {"ORIGIN_NOT_ALLOWED", "MCP_SESSION_REQUIRED"} <= STABLE_CODES
    # 23 -> 24 (003-correction-delete-ux): ALREADY_RESOLVED reports the
    # idempotent state of an already-decided review item (R9).
    assert len(STABLE_CODES) == 24
    for code in STABLE_CODES - {"JOB_ACCEPTED"}:
        response = safe_error(BrainError(code), correlation_id="corr-1")
        assert response["code"] == code
        assert response["status"] in {"rejected", "failed", "unavailable", "conflict"}
        assert response["request_id"] == "corr-1"
        assert response["message"]


def test_untrusted_exception_content_is_not_exposed():
    marker = "never-print-a-private-body"
    response = safe_error(ValueError(marker), correlation_id="corr-2")
    assert marker not in repr(response)
    assert response["code"] == "INTERNAL_SAFE_ERROR"
    assert response["retryable"] is False


def test_conflict_and_unavailable_have_distinct_statuses():
    assert safe_error(BrainError("VERSION_CONFLICT"))["status"] == "conflict"
    assert safe_error(BrainError("BRAIN_UNAVAILABLE"))["status"] == "unavailable"
    assert safe_error(BrainError("BRAIN_UNAVAILABLE"), retry_after=30)["retry_after"] == 30
    assert "retry_after" not in safe_error(BrainError("AUTH_INVALID"), retry_after=30)
