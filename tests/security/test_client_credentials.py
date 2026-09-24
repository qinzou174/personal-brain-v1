"""Credential invariants for internal opaque-token clients (T022)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from personal_brain_domain.common.errors import BrainError
from personal_brain_domain.security.clients import (
    Client,
    authenticate,
    issue_credential,
    record_client_use,
    revoke_client,
    revoke_credential,
    rotate_credential,
    validate_rotation_overlap,
    verify_permission_epoch,
)


NOW = datetime(2026, 9, 23, tzinfo=timezone.utc)


def client():
    return Client(id="client-a", owner_id="owner-a", status="active", permission_epoch=7,
                  allowed_scopes=frozenset({"personal"}), allowed_tools=frozenset({"get_note"}))


def test_opaque_token_is_random_and_only_verifier_is_stored():
    token, credential = issue_credential(client(), now=NOW)
    other, _ = issue_credential(client(), now=NOW)
    assert token != other
    assert len(token) >= 32
    assert token not in repr(credential)
    assert token not in credential.verifier
    assert credential.verifier.startswith("$argon2id$")
    assert authenticate(client(), [credential], token, now=NOW) == client()


@pytest.mark.parametrize("candidate", [None, "", "wrong"])
def test_missing_or_invalid_token_rejected(candidate):
    token, credential = issue_credential(client(), now=NOW)
    assert token
    with pytest.raises(BrainError) as caught:
        authenticate(client(), [credential], candidate, now=NOW)
    assert caught.value.code in {"AUTH_REQUIRED", "AUTH_INVALID"}


def test_expired_or_revoked_credential_rejected():
    token, credential = issue_credential(client(), now=NOW, expires_at=NOW + timedelta(hours=1))
    for changed, at in (
        (credential, NOW + timedelta(hours=1)),
        (replace(credential, revoked_at=NOW), NOW),
    ):
        with pytest.raises(BrainError) as caught:
            authenticate(client(), [changed], token, now=at)
        assert caught.value.code == "AUTH_INVALID"


def test_rotation_overlap_is_bounded_and_old_token_expires():
    old_token, old = issue_credential(client(), now=NOW)
    new_token, old_during_overlap, new = rotate_credential(
        client(), old, now=NOW + timedelta(minutes=1), overlap=timedelta(hours=1)
    )
    assert authenticate(client(), [old_during_overlap, new], old_token, now=NOW + timedelta(minutes=30))
    assert authenticate(client(), [old_during_overlap, new], new_token, now=NOW + timedelta(hours=2))
    with pytest.raises(BrainError):
        authenticate(client(), [old_during_overlap, new], old_token, now=NOW + timedelta(hours=2))
    with pytest.raises(ValueError):
        rotate_credential(client(), old, now=NOW, overlap=timedelta(hours=24, seconds=1))


def test_revoke_cancels_all_rotation_overlap_and_stale_context():
    old_token, old = issue_credential(client(), now=NOW)
    new_token, old, new = rotate_credential(client(), old, now=NOW, overlap=timedelta(hours=24))
    revoked = revoke_client(client(), now=NOW + timedelta(minutes=1))
    assert revoked.permission_epoch == 8
    for token in (old_token, new_token):
        with pytest.raises(BrainError) as caught:
            authenticate(revoked, [old, new], token, now=NOW + timedelta(minutes=2))
        assert caught.value.code == "CLIENT_REVOKED"
    with pytest.raises(BrainError) as caught:
        verify_permission_epoch(revoked, authenticated_epoch=7)
    assert caught.value.code == "CLIENT_REVOKED"


def test_epoch_change_rejects_running_client_context():
    changed = replace(client(), permission_epoch=8)
    with pytest.raises(BrainError) as caught:
        verify_permission_epoch(changed, authenticated_epoch=7)
    assert caught.value.code == "AUTH_INVALID"


def test_revoke_single_credential_and_track_last_use():
    token, credential = issue_credential(client(), now=NOW)
    used = record_client_use(client(), now=NOW + timedelta(minutes=1))
    assert used.last_used_at == NOW + timedelta(minutes=1)
    assert record_client_use(used, now=NOW) == used
    with pytest.raises(BrainError) as caught:
        authenticate(used, [revoke_credential(credential, now=NOW)], token, now=NOW)
    assert caught.value.code == "AUTH_INVALID"


def test_malformed_verifier_fails_closed():
    token, credential = issue_credential(client(), now=NOW)
    with pytest.raises(BrainError) as caught:
        authenticate(client(), [replace(credential, verifier="bad-hash")], token, now=NOW)
    assert caught.value.code == "AUTH_INVALID"


def test_overlap_boundary_is_inclusive():
    assert validate_rotation_overlap(NOW, NOW + timedelta(hours=24))
    assert not validate_rotation_overlap(NOW, NOW + timedelta(hours=24, seconds=1))
