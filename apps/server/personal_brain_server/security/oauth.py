"""OAuth 2.0 authorization-code + PKCE S256 resource server (V1 gateway).

FR-066..FR-075/FR-098/ER-06: discovery binds exactly one protected resource to
its authorization server; authorization codes require PKCE S256, an exact
redirect URI, a matching resource and explicit owner confirmation; tokens are
scoped, audience-bound, single-use codes, and revoking a client invalidates all
its tokens via a monotonic permission epoch.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

from personal_brain_domain.common.errors import BrainError


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _digest(verifier: str) -> str:
    return _b64u(hashlib.sha256(verifier.encode("ascii")).digest())


@dataclass
class _AuthorizationCode:
    client_id: str
    redirect_uri: str
    code_challenge: str
    scopes: frozenset[str]
    resource: str
    expires_at: datetime
    used: bool = False


@dataclass
class _Token:
    client_id: str
    scopes: frozenset[str]
    resource: str
    permission_epoch: int
    expires_at: datetime
    revoked: bool = False


@dataclass
class OAuthServer:
    issuer: str
    resource: str
    owner_id: str
    registered_redirect_uris: Mapping[str, frozenset[str]]
    allowed_scopes: Mapping[str, frozenset[str]] = field(default_factory=dict)
    code_ttl_seconds: int = 300
    token_ttl_seconds: int = 3600
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(timezone.utc), repr=False)
    grant_store: Any | None = field(default=None, repr=False)
    _codes: dict[str, _AuthorizationCode] = field(default_factory=dict)
    _tokens: dict[str, _Token] = field(default_factory=dict)
    _revoked: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not self.issuer or not self.resource or not self.owner_id:
            raise ValueError("issuer, resource and owner_id are required")
        if not 30 <= self.code_ttl_seconds <= 600 or not 60 <= self.token_ttl_seconds <= 86_400:
            raise ValueError("OAuth expiry bounds are invalid")

    def protected_resource_metadata(self) -> dict[str, object]:
        return {
            "resource": self.resource,
            "authorization_servers": [self.issuer],
        }

    def authorization_server_metadata(self) -> dict[str, object]:
        return {
            "issuer": self.issuer,
            "authorization_endpoint": f"{self.issuer}/authorize",
            "token_endpoint": f"{self.issuer}/token",
            "code_challenge_methods_supported": ["S256"],
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "revocation_endpoint": f"{self.issuer}/revoke",
        }

    def issue_code(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        code_challenge: str,
        code_challenge_method: str,
        scopes: set[str],
        resource: str,
        owner_confirmed: bool,
    ) -> str:
        if not owner_confirmed:
            raise BrainError("CONFIRMATION_REQUIRED")
        if code_challenge_method != "S256" or not code_challenge:
            raise BrainError("AUTH_INVALID")
        if resource != self.resource:
            raise BrainError("AUTH_INVALID")
        if redirect_uri not in self.registered_redirect_uris.get(client_id, frozenset()):
            raise BrainError("AUTH_INVALID")
        configured_scopes = self.allowed_scopes.get(client_id)
        if configured_scopes is not None and not scopes <= configured_scopes:
            raise BrainError("SCOPE_DENIED")
        if client_id in self._revoked:
            raise BrainError("CLIENT_REVOKED")
        code = secrets.token_urlsafe(32)
        self._codes[code] = _AuthorizationCode(
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            scopes=frozenset(scopes),
            resource=resource,
            expires_at=self.clock() + timedelta(seconds=self.code_ttl_seconds),
        )
        return code

    def exchange_code(
        self,
        *,
        code: str,
        client_id: str,
        redirect_uri: str,
        code_verifier: str,
        resource: str,
        current_epoch: int = 0,
    ) -> "TokenResponse":
        record = self._codes.get(code)
        if record is None or record.used or record.client_id != client_id or self.clock() >= record.expires_at:
            raise BrainError("AUTH_INVALID")
        if record.redirect_uri != redirect_uri:
            raise BrainError("AUTH_INVALID")
        if not hmac.compare_digest(_digest(code_verifier), record.code_challenge):
            raise BrainError("AUTH_INVALID")
        if resource != self.resource:
            raise BrainError("AUTH_INVALID")
        if client_id in self._revoked:
            raise BrainError("CLIENT_REVOKED")
        record.used = True
        expires_at = self.clock() + timedelta(seconds=self.token_ttl_seconds)
        if self.grant_store is not None:
            token = self.grant_store.issue(
                client_id=client_id, owner_id=self.owner_id, issuer=self.issuer,
                resource=self.resource, scopes=record.scopes, permission_epoch=current_epoch,
                expires_at=expires_at,
            )
        else:
            token = secrets.token_urlsafe(48)
            self._tokens[token] = _Token(
                client_id=client_id, scopes=record.scopes, resource=self.resource,
                permission_epoch=current_epoch, expires_at=expires_at,
            )
        return TokenResponse(access_token=token, scope=" ".join(sorted(record.scopes)),
                             expires_in=self.token_ttl_seconds)

    def verify_token(self, token: str, *, resource: str, current_epoch: int) -> "VerifiedToken":
        if self.grant_store is not None:
            client_id, scopes = self.grant_store.verify(
                token=token, resource=resource, current_epoch=current_epoch, now=self.clock(),
            )
            return VerifiedToken(client_id=client_id, scopes=frozenset(scopes))
        record = self._tokens.get(token)
        if record is None or record.resource != resource or record.revoked or self.clock() >= record.expires_at:
            raise BrainError("AUTH_INVALID")
        if record.client_id in self._revoked:
            raise BrainError("CLIENT_REVOKED")
        if record.permission_epoch != current_epoch:
            raise BrainError("AUTH_INVALID")
        return VerifiedToken(client_id=record.client_id, scopes=record.scopes)

    def revoke_client(self, client_id: str) -> None:
        self._revoked.add(client_id)
        if self.grant_store is not None:
            self.grant_store.revoke_client(client_id=client_id, now=self.clock())

    def revoke_token(self, token: str) -> None:
        if self.grant_store is not None:
            self.grant_store.revoke_token(token=token, now=self.clock())
            return
        record = self._tokens.get(token)
        if record is not None:
            record.revoked = True


@dataclass(frozen=True)
class TokenResponse:
    access_token: str
    scope: str
    expires_in: int


@dataclass(frozen=True)
class VerifiedToken:
    client_id: str
    scopes: frozenset[str]
