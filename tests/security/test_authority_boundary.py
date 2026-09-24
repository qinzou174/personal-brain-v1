"""Red-first security boundary tests for FR-067..FR-076.

The tested API deliberately performs policy resolution before the repository is
given a protected identifier. Denials must not disclose whether it exists.
"""

import pytest


class SpyRepository:
    def __init__(self):
        self.read_calls = []

    def read_by_id(self, record_id, predicate):
        self.read_calls.append((record_id, predicate))
        return {"id": record_id, "body": "private body"}


@pytest.fixture
def active_client():
    return {
        "client_id": "client-a",
        "owner_id": "owner-a",
        "status": "active",
        "permission_epoch": 7,
        "authenticated_epoch": 7,
        "allowed_tools": ["get_note"],
        "allowed_scopes": ["personal"],
    }


def test_explicit_deny_never_reads_repository(active_client):
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_infra.persistence.scoped_repository import authorized_read

    repository = SpyRepository()
    grants = [
        {"client_id": "client-a", "effect": "allow", "tool_pattern": "get_note", "scope_pattern": "personal", "sensitivity_ceiling": "private"},
        {"client_id": "client-a", "effect": "deny", "tool_pattern": "get_note", "scope_pattern": "personal", "sensitivity_ceiling": "private"},
    ]
    with pytest.raises(BrainError) as caught:
        authorized_read(active_client, grants, "get_note", "personal", "private", repository, "nonexistent-or-private")
    assert caught.value.code in {"TOOL_DENIED", "SCOPE_DENIED", "SENSITIVITY_DENIED"}
    assert repository.read_calls == []
    assert "nonexistent-or-private" not in str(caught.value)


@pytest.mark.parametrize("change", [{"status": "revoked"}, {"permission_epoch": 8}])
def test_revoked_or_stale_epoch_rejected_before_repository(active_client, change):
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_infra.persistence.scoped_repository import authorized_read

    repository = SpyRepository()
    client = active_client | change
    with pytest.raises(BrainError) as caught:
        authorized_read(client, [], "get_note", "personal", "normal", repository, "record-1")
    assert caught.value.code in {"CLIENT_REVOKED", "AUTH_INVALID"}
    assert repository.read_calls == []


def test_safe_error_contains_code_but_no_body_or_token():
    from personal_brain_domain.common.errors import safe_error

    marker = "never-disclose-this-secret-token"
    response = safe_error(ValueError(marker), code="INTERNAL_SAFE_ERROR", correlation_id="corr-1")
    encoded = repr(response)
    assert response["code"] == "INTERNAL_SAFE_ERROR"
    assert response["correlation_id"] == "corr-1"
    assert marker not in encoded


def test_audit_whitelist_omits_body_and_credential():
    from personal_brain_domain.security.audit import build_audit_event

    marker = "never-disclose-this-secret-token"
    event = build_audit_event(
        client_id="client-a",
        action="get_note",
        scope="personal",
        outcome="denied",
        duration_ms=5,
        correlation_id="corr-1",
        request_body=marker,
        credential=marker,
    )
    encoded = repr(event)
    assert marker not in encoded
    assert "request_body" not in encoded
    assert "credential" not in encoded
    assert "client-a" in encoded
