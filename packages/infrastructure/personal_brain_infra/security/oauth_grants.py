"""Persisted OAuth bearer grants backed by the migration-owned authority schema."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping
from uuid import UUID, uuid4

import sqlalchemy as sa
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from personal_brain_domain.common.errors import BrainError


class PersistedOAuthGrantStore:
    def __init__(self, session_factory: Any, tables: Mapping[str, sa.Table]) -> None:
        required = {"clients", "oauth_grants"}
        if not required <= set(tables):
            raise RuntimeError(f"OAuth schema missing tables: {sorted(required - set(tables))}")
        self._factory = session_factory
        self._clients = tables["clients"]
        self._grants = tables["oauth_grants"]
        self._hasher = PasswordHasher()

    @staticmethod
    def _db_id(table: sa.Table, column: str, value: UUID) -> UUID | str:
        kind = table.c[column].type
        if isinstance(kind, sa.Uuid) and kind.as_uuid:
            return value
        return str(value)

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

    def issue(self, *, client_id: str, owner_id: str, issuer: str, resource: str,
              scopes: Iterable[str], permission_epoch: int, expires_at: datetime) -> str:
        grant_id, secret = uuid4(), secrets.token_urlsafe(48)
        client_key = self._db_id(self._clients, "id", UUID(str(client_id)))
        owner_key = self._db_id(self._clients, "owner_id", UUID(str(owner_id)))
        with self._factory.begin() as session:
            client = session.execute(sa.select(self._clients).where(
                self._clients.c.id == client_key, self._clients.c.owner_id == owner_key,
                self._clients.c.status == "active",
            )).mappings().one_or_none()
            if client is None or int(client["permission_epoch"]) != permission_epoch:
                raise BrainError("AUTH_INVALID")
            session.execute(self._grants.insert().values(
                id=self._db_id(self._grants, "id", grant_id),
                owner_id=self._db_id(self._grants, "owner_id", UUID(str(owner_id))),
                client_id=self._db_id(self._grants, "client_id", UUID(str(client_id))),
                issuer=issuer, oauth_client_id=f"{permission_epoch}:{self._hasher.hash(secret)}", audience=resource,
                scopes=list(scopes), expires_at=expires_at, revoked_at=None,
            ))
        return f"{grant_id}.{secret}"

    def verify(self, *, token: str, resource: str, current_epoch: int,
               now: datetime) -> tuple[str, frozenset[str]]:
        try:
            raw_id, secret = token.split(".", 1)
            grant_id = UUID(raw_id)
        except (ValueError, AttributeError) as error:
            raise BrainError("AUTH_INVALID") from error
        with self._factory() as session:
            row = session.execute(sa.select(self._grants, self._clients).join(
                self._clients, self._clients.c.id == self._grants.c.client_id,
            ).where(self._grants.c.id == self._db_id(self._grants, "id", grant_id))).mappings().one_or_none()
        if row is None or row["status"] != "active" or row["revoked_at"] is not None:
            raise BrainError("AUTH_INVALID")
        if row["audience"] != resource or self._aware(row["expires_at"]) <= now:
            raise BrainError("AUTH_INVALID")
        try:
            issued_epoch_text, verifier = row["oauth_client_id"].split(":", 1)
            issued_epoch = int(issued_epoch_text)
        except (ValueError, AttributeError) as error:
            raise BrainError("AUTH_INVALID") from error
        if int(row["permission_epoch"]) != current_epoch or issued_epoch != current_epoch:
            raise BrainError("AUTH_INVALID")
        try:
            self._hasher.verify(verifier, secret)
        except (InvalidHashError, VerificationError, VerifyMismatchError) as error:
            raise BrainError("AUTH_INVALID") from error
        return str(row["client_id"]), frozenset(row["scopes"])

    def resolve_identity(
        self, *, token: str, resource: str, now: datetime,
    ) -> tuple[str, str, int, frozenset[str]]:
        """Resolve an OAuth bearer grant to ``(owner_id, client_id, epoch, scopes)``.

        The protocol adapter uses this to build the same owner-bound context an
        opaque credential would yield, so tool/scope authorization and the
        body-free audit stay on one code path (ER-06/T182).
        """
        try:
            raw_id, secret = token.split(".", 1)
            grant_id = UUID(raw_id)
        except (ValueError, AttributeError) as error:
            raise BrainError("AUTH_INVALID") from error
        with self._factory() as session:
            row = session.execute(sa.select(self._grants, self._clients).join(
                self._clients, self._clients.c.id == self._grants.c.client_id,
            ).where(self._grants.c.id == self._db_id(self._grants, "id", grant_id))).mappings().one_or_none()
        if row is None or row["status"] != "active" or row["revoked_at"] is not None:
            raise BrainError("AUTH_INVALID")
        if row["audience"] != resource or self._aware(row["expires_at"]) <= now:
            raise BrainError("AUTH_INVALID")
        try:
            issued_epoch_text, verifier = row["oauth_client_id"].split(":", 1)
            issued_epoch = int(issued_epoch_text)
        except (ValueError, AttributeError) as error:
            raise BrainError("AUTH_INVALID") from error
        if issued_epoch != int(row["permission_epoch"]):
            raise BrainError("AUTH_INVALID")
        try:
            self._hasher.verify(verifier, secret)
        except (InvalidHashError, VerificationError, VerifyMismatchError) as error:
            raise BrainError("AUTH_INVALID") from error
        return (
            str(row["owner_id"]), str(row["client_id"]),
            int(row["permission_epoch"]), frozenset(row["scopes"]),
        )

    def revoke_token(self, *, token: str, now: datetime) -> None:
        try:
            grant_id = UUID(token.split(".", 1)[0])
        except (ValueError, AttributeError) as error:
            raise BrainError("AUTH_INVALID") from error
        with self._factory.begin() as session:
            result = session.execute(self._grants.update().where(
                self._grants.c.id == self._db_id(self._grants, "id", grant_id),
                self._grants.c.revoked_at.is_(None),
            ).values(revoked_at=now))
            if result.rowcount != 1:
                raise BrainError("AUTH_INVALID")

    def revoke_client(self, *, client_id: str, now: datetime) -> None:
        client_uuid = UUID(str(client_id))
        with self._factory.begin() as session:
            session.execute(self._grants.update().where(
                self._grants.c.client_id == self._db_id(self._grants, "client_id", client_uuid),
                self._grants.c.revoked_at.is_(None),
            ).values(revoked_at=now))
            session.execute(self._clients.update().where(
                self._clients.c.id == self._db_id(self._clients, "id", client_uuid),
            ).values(status="revoked", revoked_at=now,
                     permission_epoch=self._clients.c.permission_epoch + 1))
