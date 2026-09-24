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


def test_rebuild_index_enqueues_one_job_per_record_and_is_repeatable():
    """The rebuild entry must actually press: one durable job per canonical record."""
    from personal_brain_server.admin import rebuild_index

    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    owner_id = uuid4()
    sa.Table("owners", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True))
    sa.Table(
        "raw_inputs", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("lifecycle_state", sa.String, nullable=False), sa.Column("content_text", sa.Text),
    )
    sa.Table(
        "todos", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("lifecycle_state", sa.String, nullable=False),
    )
    sa.Table(
        "self_claims", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("lifecycle_state", sa.String, nullable=False),
    )
    for name in ("projects", "project_tasks", "checkpoints", "workspace_observations"):
        sa.Table(name, metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
                 sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=False))
    sa.Table(
        "jobs", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("client_id", sa.Uuid(as_uuid=True)), sa.Column("job_type", sa.String, nullable=False),
        sa.Column("payload_ref", sa.Text, nullable=False),
        sa.Column("idempotency_key", sa.Uuid(as_uuid=True)), sa.Column("state", sa.String, nullable=False),
        sa.Column("priority", sa.Integer, nullable=False), sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("max_attempts", sa.Integer, nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_token", sa.Integer, nullable=False),
    )
    metadata.create_all(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    kept = uuid4()
    with factory.begin() as session:
        session.execute(metadata.tables["owners"].insert().values(id=owner_id))
        session.execute(metadata.tables["raw_inputs"].insert().values(
            id=kept, owner_id=owner_id, lifecycle_state="active", content_text="可检索的笔记",
        ))
        session.execute(metadata.tables["raw_inputs"].insert().values(
            id=uuid4(), owner_id=owner_id, lifecycle_state="deleted", content_text="已删除的笔记",
        ))
        session.execute(metadata.tables["todos"].insert().values(
            id=uuid4(), owner_id=owner_id, lifecycle_state="active",
        ))
        session.execute(metadata.tables["self_claims"].insert().values(
            id=uuid4(), owner_id=owner_id, lifecycle_state="superseded",
        ))
        session.execute(metadata.tables["projects"].insert().values(id=uuid4(), owner_id=owner_id))

    first = rebuild_index(factory, metadata.tables)

    assert first == {"scanned": 3, "enqueued": 3, "skipped_active": 0}
    with factory() as session:
        rows = [dict(row) for row in session.execute(sa.select(metadata.tables["jobs"])).mappings().all()]
    assert {row["job_type"] for row in rows} == {"rebuild_index"}
    refs = {row["payload_ref"] for row in rows}
    assert f"raw_input:{kept}" in refs
    assert sum(1 for ref in refs if ref.startswith("todo:")) == 1
    assert sum(1 for ref in refs if ref.startswith("project:")) == 1
    assert not any("deleted" in ref for ref in refs)
    assert all(row["state"] == "queued" for row in rows)

    # Pressing it twice never double-queues the same record.
    second = rebuild_index(factory, metadata.tables)
    assert second == {"scanned": 3, "enqueued": 0, "skipped_active": 3}
    engine.dispose()


def test_review_access_grant_unlocks_the_governance_gate_on_a_content_scope(tmp_path):
    """D1: governance tools authorize the data scope, so the gate needs a switch."""
    from personal_brain_infra.security.authority import PersistedAuthority
    from personal_brain_server.admin import provision_client, set_review_access

    engine, factory, metadata = _database()
    credential_file = tmp_path / "zafiro.credential"
    provisioned = provision_client(
        factory, metadata.tables, display_name="Zafiro", client_type="mobile",
        credential_file=credential_file,
    )
    token = credential_file.read_text(encoding="utf-8").strip()
    authority = PersistedAuthority(factory, metadata.tables)
    context = authority.authenticate(token)

    # The initial least-privilege profile cannot govern knowledge data: the call
    # is denied before the high-risk confirmation gate is ever reached.
    with pytest.raises(BrainError) as denied:
        authority.authorize(context, tool="review.write", scope="knowledge",
                            sensitivity="private", risk="high_risk_deletion")
    assert denied.value.code == "SCOPE_DENIED"

    with pytest.raises(BrainError) as unconfirmed:
        set_review_access(
            factory, metadata.tables, client_id=provisioned["client_id"], scope="knowledge",
            access="write", confirmed_client_id=provisioned["client_id"], confirmed_scope="self",
        )
    assert unconfirmed.value.code == "CONFIRMATION_REQUIRED"

    set_review_access(
        factory, metadata.tables, client_id=provisioned["client_id"], scope="knowledge",
        access="write", confirmed_client_id=provisioned["client_id"], confirmed_scope="knowledge",
    )

    context = authority.authenticate(token)
    # create_review_item's ordinary-risk path now authorizes on the content scope…
    assert authority.authorize(context, tool="review.write", scope="knowledge", sensitivity="private")
    # …and create_deletion_plan reaches the ER-06 confirmation gate instead of SCOPE_DENIED.
    with pytest.raises(BrainError) as gated:
        authority.authorize(context, tool="review.write", scope="knowledge",
                            sensitivity="private", risk="high_risk_deletion")
    assert gated.value.code == "CONFIRMATION_REQUIRED"

    from personal_brain_server.api.authorized_tools import AuthorizedToolService
    from types import SimpleNamespace

    stored = []

    def fake_store(**kwargs):
        stored.append(kwargs)
        return SimpleNamespace(create_deletion_plan=lambda **_: {
            "status": "accepted", "plan_id": "p-1", "review_item_id": "r-1",
            "execution_state": "preview", "confirmation_state": "pending",
        })

    service = AuthorizedToolService(authority, fake_store)
    plan = service.create_deletion_plan(
        credential=token, targets=[["raw_input", str(uuid4())]], dependents={},
        requested_scope="knowledge", idempotency_key=uuid4(),
    )
    # The proposal reaches the store (it destroys nothing) and answers the gate
    # with the pending plan + its single-use confirmation item.
    assert stored and plan["confirmation_required"] is True
    assert plan["confirmation_state"] == "pending" and plan["review_item_id"] == "r-1"

    set_review_access(
        factory, metadata.tables, client_id=provisioned["client_id"], scope="knowledge",
        access="none", confirmed_client_id=provisioned["client_id"], confirmed_scope="knowledge",
    )
    with pytest.raises(BrainError) as revoked:
        authority.authorize(authority.authenticate(token), tool="review.write", scope="knowledge",
                            sensitivity="private", risk="high_risk_deletion")
    assert revoked.value.code == "SCOPE_DENIED"
    with factory() as session:
        actions = set(session.scalars(sa.select(metadata.tables["audit_events"].c.action)))
    assert {"grant_review_access", "revoke_review_access"} <= actions
    engine.dispose()
