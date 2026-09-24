"""Runtime OAuth bearer resolution that yields the owner-bound authority context.

T182/ER-06: remote clients authenticate through the protocol adapter.  A verified
OAuth grant maps to the same ``AuthorityContext`` an opaque credential would
produce, so tool/scope authorization and the body-free audit stay on one code
path.  A grant-shaped token that fails verification is rejected outright and
never falls back to the opaque branch.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from personal_brain_domain.common.errors import BrainError
from personal_brain_infra.security.authority import AuthorityContext
from personal_brain_infra.security.oauth_grants import PersistedOAuthGrantStore


class OAuthBearerAuthority:
    """Resolve OAuth bearer grants; delegate opaque credentials unchanged."""

    def __init__(
        self,
        *,
        grant_store: PersistedOAuthGrantStore,
        opaque: Any,
        resource: str,
    ) -> None:
        self._grant_store = grant_store
        self._opaque = opaque
        self._resource = resource

    @staticmethod
    def _looks_like_grant(token: str) -> bool:
        try:
            raw_id, _secret = token.split(".", 1)
            UUID(raw_id)
        except (ValueError, AttributeError):
            return False
        return True

    def authenticate(
        self, token: str, *, now: datetime | None = None, resource: str | None = None,
    ) -> AuthorityContext:
        if not token:
            raise BrainError("AUTH_INVALID")
        if self._looks_like_grant(token):
            owner_id, client_id, epoch, _scopes = self._grant_store.resolve_identity(
                token=token, resource=resource or self._resource,
                now=now or _utcnow(),
            )
            return AuthorityContext(
                owner_id=owner_id, client_id=client_id, authenticated_epoch=epoch,
            )
        return self._opaque.authenticate(token, now=now)

    def authorize(self, context: AuthorityContext, *, tool: str, scope: str,
                  sensitivity: str, now: datetime | None = None,
                  risk: str = "ordinary") -> bool:
        return self._opaque.authorize(
            context, tool=tool, scope=scope, sensitivity=sensitivity, now=now, risk=risk,
        )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)