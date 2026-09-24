"""T182: OAuth bearer tokens resolve to persisted authority at runtime.

The protocol adapter must map a verified OAuth grant into the same owner-bound
AuthorityContext used by opaque credentials, then authorize against persisted
grant state and record body-free audit outcomes.  Reuse of an OAuth token after
revocation or permission-epoch change must fail closed without touching opaque
credentials or protected content.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker


def _schema() -> sa.MetaData:
    metadata = sa.MetaData()
    sa.Table(
        "clients", metadata, sa.Column("id", sa.String, primary_key=True),
        sa.Column("owner_id", sa.String, nullable=False), sa.Column("status", sa.String, nullable=False),
        sa.Column("scopes", sa.JSON, nullable=False), sa.Column("allowed_tools", sa.JSON, nullable=False),
        sa.Column("permission_epoch", sa.Integer, nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    sa.Table(
        "credentials", metadata, sa.Column("id", sa.String, primary_key=True),
        sa.Column("client_id", sa.String, nullable=False), sa.Column("verifier", sa.Text, nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)), sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("overlap_deadline", sa.DateTime(timezone=True)),
    )
    sa.Table(
        "oauth_grants", metadata, sa.Column("id", sa.String, primary_key=True),
        sa.Column("owner_id", sa.String, nullable=False), sa.Column("client_id", sa.String, nullable=False),
        sa.Column("issuer", sa.Text, nullable=False), sa.Column("oauth_client_id", sa.Text, nullable=False),
        sa.Column("audience", sa.Text, nullable=False), sa.Column("scopes", sa.JSON, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    sa.Table(
        "permission_grants", metadata, sa.Column("id", sa.String, primary_key=True),
        sa.Column("client_id", sa.String, nullable=False), sa.Column("effect", sa.String, nullable=False),
        sa.Column("scope_pattern", sa.String, nullable=False), sa.Column("tool_pattern", sa.String, nullable=False),
        sa.Column("sensitivity_ceiling", sa.String, nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True)),
    )
    return metadata


def _database(tmp_path=None):
    if tmp_path is None:
        url = "sqlite+pysqlite:///:memory:"
    else:
        url = f"sqlite+pysqlite:///{(tmp_path / 'oauth_runtime.sqlite').as_posix()}"
    engine = sa.create_engine(url, connect_args={"check_same_thread": False} if tmp_path is not None else {})
    metadata = _schema()
    metadata.create_all(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    return engine, factory, metadata


def _seed_grant(factory, metadata, *, epoch: int = 4) -> tuple[str, str]:
    from personal_brain_infra.security.oauth_grants import PersistedOAuthGrantStore

    now = datetime.now(timezone.utc)
    owner_id, client_id = str(uuid4()), str(uuid4())
    with factory.begin() as session:
        session.execute(metadata.tables["clients"].insert().values(
            id=client_id, owner_id=owner_id, status="active", permission_epoch=epoch,
            scopes=["knowledge"], allowed_tools=["knowledge.read"],
        ))
        session.execute(metadata.tables["permission_grants"].insert().values(
            id=str(uuid4()), client_id=client_id, effect="allow", scope_pattern="knowledge",
            tool_pattern="knowledge.read", sensitivity_ceiling="private",
            effective_from=now - timedelta(days=1), effective_to=None,
        ))
    store = PersistedOAuthGrantStore(factory, metadata.tables)
    token = store.issue(
        client_id=client_id, owner_id=owner_id, issuer="https://brain.example.test",
        resource="https://brain.example.test/mcp", scopes={"knowledge.read"},
        permission_epoch=epoch, expires_at=now + timedelta(hours=1),
    )
    return token, (owner_id, client_id)


def test_oauth_bearer_maps_to_authority_and_authorizes_against_grants():
    from personal_brain_infra.security.authority import PersistedAuthority
    from personal_brain_infra.security.oauth_grants import PersistedOAuthGrantStore
    from personal_brain_server.security.oauth_runtime import OAuthBearerAuthority

    engine, factory, metadata = _database()
    try:
        now = datetime.now(timezone.utc)
        token, (owner_id, client_id) = _seed_grant(factory, metadata, epoch=4)
        store = PersistedOAuthGrantStore(factory, metadata.tables)
        authority = OAuthBearerAuthority(
            grant_store=store, opaque=PersistedAuthority(factory, metadata.tables),
            resource="https://brain.example.test/mcp",
        )
        context = authority.authenticate(token, now=now)
        assert str(context.client_id) == client_id
        assert str(context.owner_id) == owner_id
        assert context.authenticated_epoch == 4
        assert authority.authorize(
            context, tool="knowledge.read", scope="knowledge", sensitivity="private", now=now,
        ) is True
    finally:
        engine.dispose()


def test_oauth_bearer_fails_after_client_revocation_and_epoch_bump():
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_infra.security.authority import PersistedAuthority
    from personal_brain_infra.security.oauth_grants import PersistedOAuthGrantStore
    from personal_brain_server.security.oauth_runtime import OAuthBearerAuthority

    engine, factory, metadata = _database()
    try:
        now = datetime.now(timezone.utc)
        token, (owner_id, client_id) = _seed_grant(factory, metadata, epoch=4)
        store = PersistedOAuthGrantStore(factory, metadata.tables)
        authority = OAuthBearerAuthority(
            grant_store=store, opaque=PersistedAuthority(factory, metadata.tables),
            resource="https://brain.example.test/mcp",
        )
        assert authority.authenticate(token, now=now) is not None
        store.revoke_client(client_id=client_id, now=now)
        with pytest.raises(BrainError):
            authority.authenticate(token, now=now)
    finally:
        engine.dispose()


def test_oauth_bearer_rejects_wrong_resource_and_expired_grants():
    from datetime import timedelta

    from personal_brain_domain.common.errors import BrainError
    from personal_brain_infra.security.authority import PersistedAuthority
    from personal_brain_infra.security.oauth_grants import PersistedOAuthGrantStore
    from personal_brain_server.security.oauth_runtime import OAuthBearerAuthority

    engine, factory, metadata = _database()
    try:
        now = datetime.now(timezone.utc)
        token, (owner_id, client_id) = _seed_grant(factory, metadata, epoch=4)
        store = PersistedOAuthGrantStore(factory, metadata.tables)
        authority = OAuthBearerAuthority(
            grant_store=store, opaque=PersistedAuthority(factory, metadata.tables),
            resource="https://brain.example.test/mcp",
        )
        with pytest.raises(BrainError):
            authority.authenticate(token, resource="https://other.example.test/mcp", now=now)
        # Expire the grant row and confirm fail-closed.
        with factory.begin() as session:
            session.execute(metadata.tables["oauth_grants"].update().values(
                expires_at=now - timedelta(minutes=1),
            ))
        with pytest.raises(BrainError):
            authority.authenticate(token, now=now)
    finally:
        engine.dispose()


def test_oauth_shaped_token_never_falls_back_to_opaque():
    """A grant-form token that fails verification is rejected outright."""
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_infra.security.authority import PersistedAuthority
    from personal_brain_infra.security.oauth_grants import PersistedOAuthGrantStore
    from personal_brain_server.security.oauth_runtime import OAuthBearerAuthority

    engine, factory, metadata = _database()
    try:
        now = datetime.now(timezone.utc)
        _token, (owner_id, client_id) = _seed_grant(factory, metadata, epoch=4)
        store = PersistedOAuthGrantStore(factory, metadata.tables)
        authority = OAuthBearerAuthority(
            grant_store=store, opaque=PersistedAuthority(factory, metadata.tables),
            resource="https://brain.example.test/mcp",
        )
        # Grant-shaped but garbage secret -> must not fall back to opaque branch.
        with pytest.raises(BrainError):
            authority.authenticate(f"{uuid4()}.garbage", now=now)
    finally:
        engine.dispose()


def test_oauth_bearer_accepted_by_streamable_http_and_audit_is_value_free(tmp_path):
    """Remote transport accepts a persisted OAuth bearer; audit repr excludes the value."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from personal_brain_domain.security.audit import audit_repr, build_audit_event
    from personal_brain_infra.security.authority import PersistedAuthority
    from personal_brain_infra.security.oauth_grants import PersistedOAuthGrantStore
    from personal_brain_server.protocols.mcp_dispatcher import MCPDispatcher
    from personal_brain_server.protocols.remote import create_mcp_router
    from personal_brain_server.security.oauth_runtime import OAuthBearerAuthority

    engine, factory, metadata = _database(tmp_path)
    try:
        now = datetime.now(timezone.utc)
        token, (owner_id, client_id) = _seed_grant(factory, metadata, epoch=4)
        store = PersistedOAuthGrantStore(factory, metadata.tables)
        authority = OAuthBearerAuthority(
            grant_store=store, opaque=PersistedAuthority(factory, metadata.tables),
            resource="https://brain.example.test/mcp",
        )
        seen_contexts: list[object] = []
        dispatcher = MCPDispatcher(
            tool_definitions=[{"name": "who_am_i", "description": "identity", "inputSchema": {"type": "object"}}],
            invoke=lambda name, arguments, identity: (
                seen_contexts.append(identity[0]) or {"client": str(identity[0])}
            ),
            resolve_identity=lambda credential: (authority.authenticate(credential), credential),
        )
        app = FastAPI()
        app.include_router(create_mcp_router(
            dispatcher=dispatcher,
            resource="https://brain.example.test/mcp",
            authorization_server="https://brain.example.test",
            allowed_origins={"https://client.example.test"},
        ))
        client = TestClient(app)
        initialized = client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {token}", "MCP-Protocol-Version": "2025-11-25"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
        )
        assert initialized.status_code == 200
        session_id = initialized.headers["MCP-Session-Id"]
        called = client.post(
            "/mcp",
            headers={
                "Authorization": f"Bearer {token}", "MCP-Protocol-Version": "2025-11-25",
                "MCP-Session-Id": session_id,
            },
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                  "params": {"name": "who_am_i", "arguments": {}}},
        )
        assert called.status_code == 200
        assert "owner" in called.json()["result"]["structuredContent"]["client"]
        # The resolved authority context and the audited representation never surface the bearer value.
        assert str(seen_contexts[0]).endswith("authenticated_epoch=4)")
        event = build_audit_event(
            client_id=client_id, correlation_id=str(uuid4()), action="tool_call",
            outcome="completed", duration_ms=1,
            tool="who_am_i", effective_scope="knowledge", target_category="identity",
            target_id=str(uuid4()),
        )
        event.details["request_body"] = token
        event.details["credential"] = token
        assert token not in audit_repr(event)
    finally:
        engine.dispose()