"""T173: protected work derives authority from credentials and persisted state."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from personal_brain_domain.security.clients import Client, issue_credential


def _authority_db():
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    clients = sa.Table(
        "clients", metadata, sa.Column("id", sa.String, primary_key=True),
        sa.Column("owner_id", sa.String, nullable=False), sa.Column("status", sa.String, nullable=False),
        sa.Column("scopes", sa.JSON, nullable=False), sa.Column("allowed_tools", sa.JSON, nullable=False),
        sa.Column("permission_epoch", sa.Integer, nullable=False),
    )
    credentials = sa.Table(
        "credentials", metadata, sa.Column("id", sa.String, primary_key=True),
        sa.Column("client_id", sa.String, nullable=False), sa.Column("verifier", sa.Text, nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)), sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("overlap_deadline", sa.DateTime(timezone=True)),
    )
    grants = sa.Table(
        "permission_grants", metadata, sa.Column("id", sa.String, primary_key=True),
        sa.Column("client_id", sa.String, nullable=False), sa.Column("effect", sa.String, nullable=False),
        sa.Column("scope_pattern", sa.String, nullable=False), sa.Column("tool_pattern", sa.String, nullable=False),
        sa.Column("sensitivity_ceiling", sa.String, nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True)),
    )
    metadata.create_all(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    client = Client(
        id="client-a", owner_id="owner-a", status="active", permission_epoch=3,
        allowed_tools=("finance.write",), allowed_scopes=("finance",),
    )
    token, credential = issue_credential(client, now=datetime.now(timezone.utc))
    with factory.begin() as session:
        session.execute(clients.insert().values(
            id=client.id, owner_id=client.owner_id, status=client.status,
            scopes=list(client.allowed_scopes), allowed_tools=list(client.allowed_tools), permission_epoch=3,
        ))
        session.execute(credentials.insert().values(
            id=str(uuid4()), client_id=client.id, verifier=credential.verifier,
            issued_at=credential.issued_at, expires_at=None, revoked_at=None, overlap_deadline=None,
        ))
        session.execute(grants.insert().values(
            id=str(uuid4()), client_id=client.id, effect="allow", scope_pattern="finance",
            tool_pattern="finance.write", sensitivity_ceiling="private", effective_from=datetime.now(timezone.utc),
        ))
    return factory, metadata, token


def test_credential_derives_identity_and_persisted_grants():
    from personal_brain_infra.security.authority import PersistedAuthority

    factory, metadata, token = _authority_db()
    authority = PersistedAuthority(factory, metadata.tables)
    context = authority.authenticate(token)
    assert context.client_id == "client-a" and context.owner_id == "owner-a"
    assert authority.authorize(context, tool="finance.write", scope="finance", sensitivity="private")


def test_native_uuid_backed_identity_authorizes_like_production_postgresql():
    """Native UUID rows must cross the string-based domain policy boundary."""
    from personal_brain_infra.security.authority import PersistedAuthority

    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    clients = sa.Table(
        "clients", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("status", sa.String, nullable=False), sa.Column("scopes", sa.JSON, nullable=False),
        sa.Column("allowed_tools", sa.JSON, nullable=False),
        sa.Column("permission_epoch", sa.Integer, nullable=False),
    )
    credentials = sa.Table(
        "credentials", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("client_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("verifier", sa.Text, nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("overlap_deadline", sa.DateTime(timezone=True)),
    )
    grants = sa.Table(
        "permission_grants", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("client_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("effect", sa.String, nullable=False),
        sa.Column("scope_pattern", sa.String, nullable=False),
        sa.Column("tool_pattern", sa.String, nullable=False),
        sa.Column("sensitivity_ceiling", sa.String, nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True)),
    )
    metadata.create_all(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    owner_id, client_id = uuid4(), uuid4()
    client = Client(
        id=str(client_id), owner_id=str(owner_id), status="active", permission_epoch=1,
        allowed_tools=frozenset({"knowledge.write"}),
        allowed_scopes=frozenset({"knowledge"}),
    )
    token, credential = issue_credential(client, now=datetime.now(timezone.utc))
    with factory.begin() as session:
        session.execute(clients.insert().values(
            id=client_id, owner_id=owner_id, status="active", scopes=["knowledge"],
            allowed_tools=["knowledge.write"], permission_epoch=1,
        ))
        session.execute(credentials.insert().values(
            id=uuid4(), client_id=client_id, verifier=credential.verifier,
            issued_at=credential.issued_at,
        ))
        session.execute(grants.insert().values(
            id=uuid4(), client_id=client_id, effect="allow", scope_pattern="knowledge",
            tool_pattern="knowledge.write", sensitivity_ceiling="private",
            effective_from=datetime.now(timezone.utc),
        ))

    authority = PersistedAuthority(factory, metadata.tables)
    context = authority.authenticate(token)
    assert context.client_id == client_id and context.owner_id == owner_id
    assert authority.authorize(
        context, tool="knowledge.write", scope="knowledge", sensitivity="private",
    )
    engine.dispose()


def test_permission_epoch_change_between_source_and_commit_fails_closed():
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_infra.security.authority import AuthorizationPipeline, PersistedAuthority

    factory, metadata, token = _authority_db()
    authority = PersistedAuthority(factory, metadata.tables)
    context = authority.authenticate(token)
    committed: list[bool] = []

    def external_call():
        with factory.begin() as session:
            session.execute(metadata.tables["clients"].update().values(permission_epoch=4))
        return "provider-result"

    pipeline = AuthorizationPipeline(authority)
    with pytest.raises(BrainError) as caught:
        pipeline.run(
            context, tool="finance.write", scope="finance", sensitivity="private",
            source_read=lambda: "source", external_call=external_call,
            canonical_commit=lambda: committed.append(True), response=lambda: "ok",
        )
    assert caught.value.code == "AUTH_INVALID"
    assert committed == []


def test_production_tool_boundary_accepts_no_caller_identity_or_grants():
    import inspect

    from personal_brain_server.api.authorized_tools import AuthorizedToolService

    parameters = inspect.signature(AuthorizedToolService.add_expense).parameters
    assert "client_id" not in parameters
    assert "grants" not in parameters
    assert "credential" in parameters
