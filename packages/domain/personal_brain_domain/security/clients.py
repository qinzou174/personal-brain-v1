"""Internal opaque-token client identity; remote OAuth mapping is separate.

The returned bearer value is shown once to the caller. Only Argon2id verifiers
belong in the credential control plane; never put the token in an ordinary
Brain record, event, exception, representation, or audit row.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

from personal_brain_domain.common.errors import BrainError


MAX_ROTATION_OVERLAP = timedelta(hours=24)
_HASHER = PasswordHasher(type=Type.ID)


def validate_rotation_overlap(issued_at: datetime, deadline: datetime) -> bool:
    interval = _utc(deadline) - _utc(issued_at)
    return timedelta(0) <= interval <= MAX_ROTATION_OVERLAP


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class Client:
    id: str
    owner_id: str
    status: str
    permission_epoch: int
    allowed_scopes: frozenset[str]
    allowed_tools: frozenset[str]
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.status not in {"active", "suspended", "revoked"} or self.permission_epoch < 0:
            raise ValueError("invalid client state")


@dataclass(frozen=True, slots=True)
class Credential:
    id: str
    client_id: str
    verifier: str
    issued_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    overlap_deadline: datetime | None = None

    def __repr__(self) -> str:
        return f"Credential(id={self.id!r}, client_id={self.client_id!r}, verifier=<redacted>)"


def issue_credential(
    client: Client, *, now: datetime, expires_at: datetime | None = None
) -> tuple[str, Credential]:
    issued_at = _utc(now)
    if client.status != "active":
        raise BrainError("CLIENT_REVOKED" if client.status == "revoked" else "AUTH_INVALID")
    if expires_at is not None and _utc(expires_at) <= issued_at:
        raise ValueError("expiry must be after issue time")
    token = secrets.token_urlsafe(48)
    credential = Credential(
        id=str(uuid4()), client_id=client.id, verifier=_HASHER.hash(token),
        issued_at=issued_at, expires_at=_utc(expires_at) if expires_at else None,
    )
    return token, credential


def verify_permission_epoch(client: Client, *, authenticated_epoch: int) -> None:
    """Call at request start and each ER-06 read/call/commit/response checkpoint."""
    if client.status == "revoked":
        raise BrainError("CLIENT_REVOKED")
    if client.status != "active" or authenticated_epoch != client.permission_epoch:
        raise BrainError("AUTH_INVALID")


def authenticate(
    client: Client,
    credentials: list[Credential] | tuple[Credential, ...],
    token: str | None,
    *,
    now: datetime,
    authenticated_epoch: int | None = None,
) -> Client:
    """Return the authenticated identity, never protected data or the token."""
    moment = _utc(now)
    if client.status == "revoked":
        raise BrainError("CLIENT_REVOKED")
    if client.status != "active":
        raise BrainError("AUTH_INVALID")
    if authenticated_epoch is not None:
        verify_permission_epoch(client, authenticated_epoch=authenticated_epoch)
    if not token:
        raise BrainError("AUTH_REQUIRED")
    if not isinstance(token, str) or len(token) > 256:
        raise BrainError("AUTH_INVALID")
    for credential in credentials:
        if credential.client_id != client.id or credential.revoked_at is not None:
            continue
        if credential.expires_at is not None and moment >= _utc(credential.expires_at):
            continue
        if credential.overlap_deadline is not None and moment >= _utc(credential.overlap_deadline):
            continue
        try:
            if _HASHER.verify(credential.verifier, token):
                return client
        except (VerificationError, InvalidHashError):
            pass
    raise BrainError("AUTH_INVALID")


def rotate_credential(
    client: Client, old: Credential, *, now: datetime, overlap: timedelta = timedelta(0)
) -> tuple[str, Credential, Credential]:
    moment = _utc(now)
    if not timedelta(0) <= overlap <= MAX_ROTATION_OVERLAP:
        raise ValueError("rotation overlap must be between zero and 24 hours")
    if old.client_id != client.id or old.revoked_at is not None:
        raise BrainError("AUTH_INVALID")
    if old.expires_at is not None and moment >= _utc(old.expires_at):
        raise BrainError("AUTH_INVALID")
    if old.overlap_deadline is not None:
        raise BrainError("AUTH_INVALID")
    token, replacement = issue_credential(client, now=moment)
    old_updated = replace(old, overlap_deadline=moment + overlap)
    return token, old_updated, replacement


def revoke_client(client: Client, *, now: datetime) -> Client:
    if client.status == "revoked":
        return client
    return replace(
        client, status="revoked", permission_epoch=client.permission_epoch + 1,
        revoked_at=_utc(now),
    )


def revoke_credential(credential: Credential, *, now: datetime) -> Credential:
    if credential.revoked_at is not None:
        return credential
    return replace(credential, revoked_at=_utc(now))


def record_client_use(client: Client, *, now: datetime) -> Client:
    if client.status != "active":
        raise BrainError("CLIENT_REVOKED" if client.status == "revoked" else "AUTH_INVALID")
    moment = _utc(now)
    if client.last_used_at is not None and moment < _utc(client.last_used_at):
        return client
    return replace(client, last_used_at=moment)
