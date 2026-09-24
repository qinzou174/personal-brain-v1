"""Persisted OAuth grant and permission-epoch acceptance for T182."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker


def _database(tmp_path):
    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'oauth.sqlite').as_posix()}")
    metadata = sa.MetaData()
    uuid = sa.Uuid(as_uuid=True)
    clients = sa.Table(
        "clients", metadata, sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False), sa.Column("status", sa.String, nullable=False),
        sa.Column("permission_epoch", sa.Integer, nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    grants = sa.Table(
        "oauth_grants", metadata, sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False), sa.Column("client_id", uuid, nullable=False),
        sa.Column("issuer", sa.Text, nullable=False), sa.Column("oauth_client_id", sa.Text, nullable=False),
        sa.Column("audience", sa.Text, nullable=False), sa.Column("scopes", sa.JSON, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    metadata.create_all(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    owner_id, client_id = uuid4(), uuid4()
    with factory.begin() as session:
        session.execute(clients.insert().values(
            id=client_id, owner_id=owner_id, status="active", permission_epoch=4,
        ))
    return engine, factory, metadata.tables, owner_id, client_id


def test_oauth_grant_survives_restart_and_token_value_is_not_stored(tmp_path):
    from personal_brain_infra.security.oauth_grants import PersistedOAuthGrantStore

    engine, factory, tables, owner_id, client_id = _database(tmp_path)
    now = datetime.now(timezone.utc)
    store = PersistedOAuthGrantStore(factory, tables)
    token = store.issue(
        client_id=str(client_id), owner_id=str(owner_id), issuer="https://brain.example.test",
        resource="https://brain.example.test/mcp", scopes={"knowledge.read"},
        permission_epoch=4, expires_at=now + timedelta(hours=1),
    )
    restarted = PersistedOAuthGrantStore(factory, tables)
    verified_client, scopes = restarted.verify(
        token=token, resource="https://brain.example.test/mcp", current_epoch=4, now=now,
    )
    assert verified_client == str(client_id) and scopes == {"knowledge.read"}
    with factory() as session:
        verifier = session.scalar(sa.select(tables["oauth_grants"].c.oauth_client_id))
    assert token not in verifier and token.split(".", 1)[1] not in verifier
    engine.dispose()


def test_oauth_grant_revocation_and_epoch_change_fail_closed(tmp_path):
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_infra.security.oauth_grants import PersistedOAuthGrantStore

    engine, factory, tables, owner_id, client_id = _database(tmp_path)
    now = datetime.now(timezone.utc)
    store = PersistedOAuthGrantStore(factory, tables)
    token = store.issue(
        client_id=str(client_id), owner_id=str(owner_id), issuer="https://brain.example.test",
        resource="https://brain.example.test/mcp", scopes={"knowledge.read"},
        permission_epoch=4, expires_at=now + timedelta(hours=1),
    )
    with factory.begin() as session:
        session.execute(tables["clients"].update().values(permission_epoch=5))
    with pytest.raises(BrainError):
        store.verify(token=token, resource="https://brain.example.test/mcp", current_epoch=5, now=now)
    store.revoke_token(token=token, now=now)
    with pytest.raises(BrainError):
        store.verify(token=token, resource="https://brain.example.test/mcp", current_epoch=4, now=now)
    engine.dispose()
