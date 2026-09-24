"""Credential-derived authority with permission-epoch race protection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

import sqlalchemy as sa
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from personal_brain_domain.common.errors import BrainError
from personal_brain_domain.security.policy import authorize as evaluate_authorization


@dataclass(frozen=True, slots=True)
class AuthorityContext:
    owner_id: Any
    client_id: Any
    authenticated_epoch: int


class PersistedAuthority:
    """Resolve opaque credentials and grants only from authoritative tables."""

    def __init__(self, session_factory: Any, tables: Mapping[str, sa.Table]) -> None:
        required = {"clients", "credentials", "permission_grants"}
        if not required <= set(tables):
            raise RuntimeError(f"authority schema missing tables: {sorted(required - set(tables))}")
        self._factory = session_factory
        self._clients = tables["clients"]
        self._credentials = tables["credentials"]
        self._grants = tables["permission_grants"]
        self._hasher = PasswordHasher()

    @staticmethod
    def _aware(value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def authenticate(self, token: str, *, now: datetime | None = None) -> AuthorityContext:
        if not token:
            raise BrainError("AUTH_INVALID")
        moment = now or datetime.now(timezone.utc)
        with self._factory() as session:
            rows = session.execute(
                sa.select(self._credentials, self._clients).join(
                    self._clients, self._clients.c.id == self._credentials.c.client_id,
                ).where(
                    self._credentials.c.revoked_at.is_(None),
                    self._clients.c.status == "active",
                )
            ).mappings()
            for row in rows:
                expires = self._aware(row.get("expires_at"))
                overlap = self._aware(row.get("overlap_deadline"))
                if expires is not None and moment >= expires:
                    continue
                if overlap is not None and moment >= overlap:
                    continue
                try:
                    matched = self._hasher.verify(row["verifier"], token)
                except (InvalidHashError, VerificationError, VerifyMismatchError):
                    matched = False
                if matched:
                    return AuthorityContext(
                        owner_id=row["owner_id"],
                        client_id=row["client_id"],
                        authenticated_epoch=int(row["permission_epoch"]),
                    )
        raise BrainError("AUTH_INVALID")

    def authorize(
        self,
        context: AuthorityContext,
        *,
        tool: str,
        scope: str,
        sensitivity: str,
        now: datetime | None = None,
        risk: str = "ordinary",
    ) -> bool:
        moment = now or datetime.now(timezone.utc)
        with self._factory() as session:
            client = session.execute(
                sa.select(self._clients).where(
                    self._clients.c.id == context.client_id,
                    self._clients.c.owner_id == context.owner_id,
                )
            ).mappings().one_or_none()
            if client is None:
                raise BrainError("AUTH_INVALID")
            grant_rows = session.execute(
                sa.select(self._grants).where(self._grants.c.client_id == context.client_id)
            ).mappings().all()
        # The production PostgreSQL schema uses native UUID columns while the
        # domain policy deliberately compares opaque string identifiers.  Keep
        # the database-native values in AuthorityContext for repository calls,
        # but normalize both sides of the policy comparison here.  Without this
        # boundary conversion authentication succeeds and every real tool call
        # fails with AUTH_INVALID even though SQLite/string-backed tests pass.
        client_record = {
            "client_id": str(client["id"]),
            "owner_id": str(client["owner_id"]),
            "status": client["status"],
            "permission_epoch": int(client["permission_epoch"]),
            "authenticated_epoch": context.authenticated_epoch,
            "allowed_tools": tuple(client["allowed_tools"]),
            "allowed_scopes": tuple(client["scopes"]),
        }
        grants = [
            {
                "client_id": str(row["client_id"]),
                "effect": row["effect"],
                "scope_pattern": row["scope_pattern"],
                "tool_pattern": row["tool_pattern"],
                "sensitivity_ceiling": row["sensitivity_ceiling"],
                "effective_from": self._aware(row["effective_from"]),
                "effective_to": self._aware(row.get("effective_to")),
            }
            for row in grant_rows
        ]
        return evaluate_authorization(
            client_record,
            grants,
            tool,
            scope,
            sensitivity,
            now=moment,
            risk=risk,
        )


class AuthorizationPipeline:
    """Recheck persisted authority before every protected side-effect stage."""

    def __init__(self, authority: PersistedAuthority) -> None:
        self._authority = authority

    def run(
        self,
        context: AuthorityContext,
        *,
        tool: str,
        scope: str,
        sensitivity: str,
        source_read: Callable[[], Any] | None,
        external_call: Callable[[], Any] | None,
        canonical_commit: Callable[[], Any],
        response: Callable[[], Any],
    ) -> Any:
        for stage in (source_read, external_call, canonical_commit):
            self._authority.authorize(
                context, tool=tool, scope=scope, sensitivity=sensitivity,
            )
            if stage is not None:
                stage()
        self._authority.authorize(
            context, tool=tool, scope=scope, sensitivity=sensitivity,
        )
        return response()
