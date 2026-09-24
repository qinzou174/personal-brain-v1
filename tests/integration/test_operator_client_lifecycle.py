"""Operator bootstrap and exact project grant lifecycle (T190/T191)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from personal_brain_domain.common.errors import BrainError


def _database():
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    common = lambda: (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    sa.Table("owners", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True), *common())
    sa.Table(
        "clients", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String, nullable=False), sa.Column("client_type", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False), sa.Column("scopes", sa.JSON, nullable=False),
        sa.Column("allowed_tools", sa.JSON, nullable=False),
        sa.Column("permission_epoch", sa.Integer, nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)), *common(),
    )
    sa.Table(
        "credentials", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("client_id", sa.Uuid(as_uuid=True), nullable=False), sa.Column("verifier", sa.Text, nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)), sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("overlap_deadline", sa.DateTime(timezone=True)), *common(),
    )
    sa.Table(
        "permission_grants", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("client_id", sa.Uuid(as_uuid=True), nullable=False), sa.Column("effect", sa.String, nullable=False),
        sa.Column("scope_pattern", sa.String, nullable=False), sa.Column("tool_pattern", sa.String, nullable=False),
        sa.Column("sensitivity_ceiling", sa.String, nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True)), sa.Column("issuer", sa.String, nullable=False),
        sa.Column("reason", sa.String), *common(),
    )
    sa.Table(
        "projects", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=False), sa.Column("name", sa.String, nullable=False),
    )
    sa.Table(
        "audit_events", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("client_id", sa.Uuid(as_uuid=True)), sa.Column("correlation_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("action", sa.String, nullable=False), sa.Column("tool", sa.String),
        sa.Column("effective_scope", sa.String), sa.Column("target_category", sa.String),
        sa.Column("target_id", sa.Uuid(as_uuid=True)), sa.Column("outcome", sa.String, nullable=False),
        sa.Column("error_code", sa.String), sa.Column("duration_ms", sa.Integer, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False), sa.Column("risk", sa.String, nullable=False),
        sa.Column("authorization_decision", sa.String),
    )
    metadata.create_all(engine)
    return engine, sessionmaker(engine, class_=Session, expire_on_commit=False), metadata


def test_operator_provisions_rotates_and_revokes_client_without_printing_token(tmp_path):
    from personal_brain_infra.security.authority import PersistedAuthority
    from personal_brain_server.admin import provision_client, revoke_client, rotate_client_credential

    engine, factory, metadata = _database()
    first_file = tmp_path / "trae.credential"
    provisioned = provision_client(
        factory, metadata.tables, display_name="TRAE CN", client_type="stdio",
        credential_file=first_file,
    )
    first_token = first_file.read_text(encoding="utf-8").strip()
    assert first_token and first_token not in repr(provisioned)
    authority = PersistedAuthority(factory, metadata.tables)
    first_context = authority.authenticate(first_token)
    assert authority.authorize(
        first_context, tool="knowledge.write", scope="knowledge", sensitivity="private",
    )
    with pytest.raises(FileExistsError):
        provision_client(factory, metadata.tables, display_name="another", client_type="stdio",
                         credential_file=first_file)

    replacement_file = tmp_path / "trae-rotated.credential"
    rotate_client_credential(
        factory, metadata.tables, client_id=provisioned["client_id"],
        credential_file=replacement_file,
    )
    replacement = replacement_file.read_text(encoding="utf-8").strip()
    with pytest.raises(BrainError):
        authority.authenticate(first_token)
    assert authority.authenticate(replacement).client_id == UUID(provisioned["client_id"])

    with pytest.raises(BrainError) as unconfirmed:
        revoke_client(factory, metadata.tables, client_id=provisioned["client_id"],
                      confirmed_client_id=uuid4())
    assert unconfirmed.value.code == "CONFIRMATION_REQUIRED"
    revoke_client(factory, metadata.tables, client_id=provisioned["client_id"],
                  confirmed_client_id=provisioned["client_id"])
    with pytest.raises(BrainError):
        authority.authenticate(replacement)
    engine.dispose()


def test_exact_project_access_requires_confirmation_and_is_revocable(tmp_path):
    from personal_brain_infra.security.authority import PersistedAuthority
    from personal_brain_server.admin import provision_client, set_project_access

    engine, factory, metadata = _database()
    credential_file = tmp_path / "cursor.credential"
    provisioned = provision_client(
        factory, metadata.tables, display_name="Cursor", client_type="stdio",
        credential_file=credential_file,
    )
    token = credential_file.read_text(encoding="utf-8").strip()
    project_id = uuid4()
    with factory.begin() as session:
        session.execute(metadata.tables["projects"].insert().values(
            id=project_id, owner_id=UUID(provisioned["owner_id"]), name="Personal Brain",
        ))
    authority = PersistedAuthority(factory, metadata.tables)
    context = authority.authenticate(token)
    scope = f"project:{project_id}"
    with pytest.raises(BrainError):
        authority.authorize(context, tool="project.read", scope=scope, sensitivity="private")
    with pytest.raises(BrainError) as unconfirmed:
        set_project_access(
            factory, metadata.tables, client_id=provisioned["client_id"], project_id=project_id,
            access="write", confirmed_client_id=provisioned["client_id"],
            confirmed_project_id=uuid4(),
        )
    assert unconfirmed.value.code == "CONFIRMATION_REQUIRED"

    set_project_access(
        factory, metadata.tables, client_id=provisioned["client_id"], project_id=project_id,
        access="write", confirmed_client_id=provisioned["client_id"],
        confirmed_project_id=project_id,
    )
    context = authority.authenticate(token)
    assert authority.authorize(context, tool="project.read", scope=scope, sensitivity="private")
    assert authority.authorize(context, tool="project.write", scope=scope, sensitivity="private")

    set_project_access(
        factory, metadata.tables, client_id=provisioned["client_id"], project_id=project_id,
        access="none", confirmed_client_id=provisioned["client_id"],
        confirmed_project_id=project_id,
    )
    with pytest.raises(BrainError):
        authority.authorize(authority.authenticate(token), tool="project.read", scope=scope,
                            sensitivity="private")
    with factory() as session:
        actions = set(session.scalars(sa.select(metadata.tables["audit_events"].c.action)))
    assert {"provision_client", "grant_project_access", "revoke_project_access"} <= actions
    engine.dispose()
