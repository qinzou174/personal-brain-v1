"""Deny-first, no implicit scope inheritance (T023)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from personal_brain_domain.common.errors import BrainError
from personal_brain_domain.security.policy import authorize, validate_confirmation_expiry


NOW = datetime(2026, 9, 23, tzinfo=timezone.utc)
CLIENT = {
    "client_id": "client-a", "status": "active", "permission_epoch": 7,
    "authenticated_epoch": 7, "allowed_tools": ["get_note"],
    "allowed_scopes": ["personal", "project:p1", "module:m1"],
}
ALLOW = {"client_id": "client-a", "effect": "allow", "tool_pattern": "get_note", "scope_pattern": "personal",
         "sensitivity_ceiling": "private"}


def test_requires_client_allowlist_and_explicit_grant():
    assert authorize(CLIENT, [ALLOW], "get_note", "personal", "private", now=NOW)
    for client, grants, tool, scope, expected in (
        (CLIENT, [], "get_note", "personal", "SCOPE_DENIED"),
        (CLIENT, [ALLOW], "delete_note", "personal", "TOOL_DENIED"),
        (CLIENT, [ALLOW], "get_note", "diary", "SCOPE_DENIED"),
    ):
        with pytest.raises(BrainError) as caught:
            authorize(client, grants, tool, scope, "normal", now=NOW)
        assert caught.value.code == expected


def test_explicit_deny_wins_even_when_allow_exists():
    with pytest.raises(BrainError) as caught:
        authorize(CLIENT, [ALLOW, ALLOW | {"effect": "deny"}], "get_note", "personal", "normal", now=NOW)
    assert caught.value.code == "TOOL_DENIED"


def test_another_clients_grant_cannot_authorize_this_client():
    with pytest.raises(BrainError) as caught:
        authorize(CLIENT, [ALLOW | {"client_id": "client-b"}], "get_note", "personal", "normal", now=NOW)
    assert caught.value.code == "SCOPE_DENIED"


def test_most_restrictive_ceiling_and_secret_exclusion():
    with pytest.raises(BrainError) as caught:
        authorize(CLIENT, [ALLOW, ALLOW | {"sensitivity_ceiling": "personal"}],
                  "get_note", "personal", "private", now=NOW)
    assert caught.value.code == "SENSITIVITY_DENIED"
    with pytest.raises(BrainError) as caught:
        authorize(CLIENT, [ALLOW], "get_note", "personal", "secret", now=NOW)
    assert caught.value.code == "SENSITIVITY_DENIED"


def test_grant_effective_window_and_epoch():
    grant = ALLOW | {"effective_from": NOW, "effective_to": NOW + timedelta(minutes=1)}
    assert authorize(CLIENT, [grant], "get_note", "personal", "normal", now=NOW)
    with pytest.raises(BrainError):
        authorize(CLIENT, [grant], "get_note", "personal", "normal", now=NOW + timedelta(minutes=1))
    with pytest.raises(BrainError) as caught:
        authorize(CLIENT | {"permission_epoch": 8}, [ALLOW], "get_note", "personal", "normal", now=NOW)
    assert caught.value.code == "AUTH_INVALID"


def test_project_grant_never_implies_personal_and_module_needs_parent():
    project = ALLOW | {"scope_pattern": "project:p1"}
    module = ALLOW | {"scope_pattern": "module:m1"}
    with pytest.raises(BrainError):
        authorize(CLIENT, [project], "get_note", "personal", "normal", now=NOW)
    with pytest.raises(BrainError) as caught:
        authorize(CLIENT, [module], "get_note", "module:m1", "normal", now=NOW,
                  parent_project_scope="project:p1")
    assert caught.value.code == "SCOPE_DENIED"
    assert authorize(CLIENT, [module, project], "get_note", "module:m1", "normal", now=NOW,
                     parent_project_scope="project:p1")


def test_high_risk_requires_separate_owner_confirmation():
    with pytest.raises(BrainError) as caught:
        authorize(CLIENT, [ALLOW], "get_note", "personal", "normal", now=NOW,
                  risk="destructive_maintenance")
    assert caught.value.code == "CONFIRMATION_REQUIRED"
    assert validate_confirmation_expiry(NOW, NOW + timedelta(minutes=15))
    assert not validate_confirmation_expiry(NOW, NOW + timedelta(minutes=15, seconds=1))
