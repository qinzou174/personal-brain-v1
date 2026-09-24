"""T171: canonical state is durable, owner-scoped, and transactionally honest."""

from __future__ import annotations

import json
import subprocess
import sys
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker


def _schema(engine, *, reject_audit: bool = False):
    metadata = sa.MetaData()
    uuid = sa.Uuid(as_uuid=True)
    common = lambda: (
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, default=1),
    )
    sa.Table("owners", metadata, sa.Column("id", uuid, primary_key=True), *common())
    sa.Table(
        "clients", metadata, sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False), sa.Column("status", sa.String, nullable=False),
        sa.Column("permission_epoch", sa.Integer, nullable=False), *common(),
    )
    sa.Table(
        "intake_requests", metadata, sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False), sa.Column("client_id", uuid, nullable=False),
        sa.Column("operation", sa.String, nullable=False), sa.Column("idempotency_key", uuid, nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False), sa.Column("content_ref", sa.Text),
        sa.Column("detected_intent", sa.String), sa.Column("declared_intent", sa.String),
        sa.Column("requested_scope", sa.String, nullable=False), sa.Column("security_decision", sa.String, nullable=False),
        sa.Column("intake_level", sa.String, nullable=False), sa.Column("state", sa.String, nullable=False),
        sa.Column("outcome_refs", sa.JSON, nullable=False), sa.Column("correlation_id", uuid, nullable=False),
        sa.Column("error_code", sa.String), *common(),
    )
    sa.Table(
        "raw_inputs", metadata, sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False), sa.Column("intake_request_id", uuid, nullable=False),
        sa.Column("client_id", uuid, nullable=False), sa.Column("content_text", sa.Text),
        sa.Column("asset_ref", sa.Text), sa.Column("content_hash", sa.String, nullable=False),
        sa.Column("original_at", sa.DateTime(timezone=True)), sa.Column("original_timezone", sa.String),
        sa.Column("source_channel", sa.String, nullable=False), sa.Column("language", sa.String),
        sa.Column("retention_policy", sa.String, nullable=False), sa.Column("sensitivity", sa.String, nullable=False),
        sa.Column("information_class", sa.String, nullable=False), sa.Column("canonicality", sa.String, nullable=False),
        sa.Column("source_kind", sa.String, nullable=False), sa.Column("source_id", uuid, nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True)), sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("lifecycle_state", sa.String, nullable=False), sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *common(),
    )
    sa.Table(
        "expenses", metadata, sa.Column("id", uuid, primary_key=True), sa.Column("owner_id", uuid, nullable=False),
        sa.Column("amount", sa.Numeric(20, 4), nullable=False), sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("category", sa.String, nullable=False), sa.Column("description", sa.String, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("occurred_timezone", sa.String, nullable=False), sa.Column("kind", sa.String, nullable=False),
        sa.Column("event_id", uuid), sa.Column("source_id", uuid, nullable=False),
        sa.Column("sensitivity", sa.String, nullable=False), sa.Column("information_class", sa.String, nullable=False),
        sa.Column("canonicality", sa.String, nullable=False), sa.Column("source_kind", sa.String, nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True)), sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("lifecycle_state", sa.String, nullable=False), sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *common(),
    )
    sa.Table(
        "todos", metadata, sa.Column("id", uuid, primary_key=True), sa.Column("owner_id", uuid, nullable=False),
        sa.Column("content", sa.String, nullable=False), sa.Column("state", sa.String, nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)), sa.Column("due_timezone", sa.String),
        sa.Column("due_window_start", sa.DateTime(timezone=True)), sa.Column("due_window_end", sa.DateTime(timezone=True)),
        sa.Column("due_precision", sa.String), sa.Column("priority", sa.Integer, nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("source_id", uuid, nullable=False), sa.Column("sensitivity", sa.String, nullable=False),
        sa.Column("information_class", sa.String, nullable=False), sa.Column("canonicality", sa.String, nullable=False),
        sa.Column("source_kind", sa.String, nullable=False), sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_to", sa.DateTime(timezone=True)), sa.Column("lifecycle_state", sa.String, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)), *common(),
    )
    sa.Table(
        "projects", metadata, sa.Column("id", uuid, primary_key=True), sa.Column("owner_id", uuid, nullable=False),
        sa.Column("name", sa.String, nullable=False), sa.Column("purpose", sa.Text, nullable=False),
        sa.Column("goals", sa.JSON, nullable=False), sa.Column("principles", sa.JSON, nullable=False),
        sa.Column("technology_summary", sa.Text), sa.Column("architecture_summary", sa.Text),
        sa.Column("deployment_summary", sa.Text), sa.Column("global_constraints", sa.JSON),
        sa.Column("directory_overview", sa.Text), sa.Column("workspace_identity", sa.String),
        sa.Column("repository_identity", sa.String), sa.Column("current_revision_evidence", sa.JSON),
        sa.Column("lifecycle_state", sa.String, nullable=False), *common(),
    )
    sa.Table(
        "project_tasks", metadata, sa.Column("id", uuid, primary_key=True), sa.Column("owner_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False), sa.Column("goal", sa.Text, nullable=False),
        sa.Column("state", sa.String, nullable=False), sa.Column("start_revision", sa.String),
        sa.Column("end_revision", sa.String), sa.Column("start_dirty_state", sa.Boolean),
        sa.Column("end_dirty_state", sa.Boolean), sa.Column("plan", sa.Text),
        sa.Column("constraints", sa.JSON), sa.Column("affected_modules", sa.JSON),
        sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("remaining_work", sa.Text), sa.Column("final_report", sa.Text), *common(),
    )
    sa.Table(
        "checkpoints", metadata, sa.Column("id", uuid, primary_key=True), sa.Column("owner_id", uuid, nullable=False),
        sa.Column("task_id", uuid, nullable=False), sa.Column("revision", sa.String),
        sa.Column("dirty_files", sa.JSON), sa.Column("changed_files", sa.JSON),
        sa.Column("completed_work", sa.Text, nullable=False), sa.Column("problems", sa.Text),
        sa.Column("decisions", sa.JSON), sa.Column("next_step", sa.Text),
        sa.Column("verification_evidence", sa.Text), sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        *common(),
    )
    sa.Table(
        "module_cards", metadata, sa.Column("id", uuid, primary_key=True), sa.Column("owner_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False), sa.Column("name", sa.String, nullable=False),
        sa.Column("paths", sa.JSON, nullable=False), sa.Column("responsibility", sa.Text),
        sa.Column("core_files", sa.JSON), sa.Column("interfaces", sa.JSON), sa.Column("dependencies", sa.JSON),
        sa.Column("consumers", sa.JSON), sa.Column("constraints", sa.JSON), sa.Column("indexed_revision", sa.String),
        sa.Column("relevant_file_hashes", sa.JSON), sa.Column("freshness", sa.String, nullable=False),
        sa.Column("stale_reasons", sa.JSON), sa.Column("refreshed_at", sa.DateTime(timezone=True)), *common(),
        sa.UniqueConstraint("owner_id", "project_id", "name"),
    )
    sa.Table(
        "workspace_observations", metadata, sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False), sa.Column("project_id", uuid, nullable=False),
        sa.Column("approved_root_identity", sa.String, nullable=False), sa.Column("revision", sa.String),
        sa.Column("branch_ref", sa.String), sa.Column("dirty_state", sa.Boolean),
        sa.Column("changed_paths", sa.JSON), sa.Column("diff_summary", sa.Text), sa.Column("file_hashes", sa.JSON),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("bridge_client_id", sa.String),
        *common(),
    )
    for fact_name in ("decisions", "constraints", "change_events"):
        sa.Table(
            fact_name, metadata, sa.Column("id", uuid, primary_key=True),
            sa.Column("owner_id", uuid, nullable=False), sa.Column("project_id", uuid, nullable=False),
            sa.Column("module_id", uuid), sa.Column("task_id", uuid), sa.Column("statement", sa.Text, nullable=False),
            sa.Column("rationale", sa.Text), sa.Column("evidence", sa.JSON), sa.Column("source_id", uuid),
            sa.Column("valid_from", sa.DateTime(timezone=True)), sa.Column("valid_to", sa.DateTime(timezone=True)),
            sa.Column("lifecycle_state", sa.String, nullable=False),
            sa.Column("deduplication_key", sa.String, nullable=False), sa.Column("affected_modules", sa.JSON),
            sa.Column("revisions", sa.JSON), *common(),
            sa.UniqueConstraint("owner_id", "deduplication_key"),
        )
    sa.Table(
        "self_claims", metadata, sa.Column("id", uuid, primary_key=True), sa.Column("owner_id", uuid, nullable=False),
        sa.Column("category", sa.String, nullable=False), sa.Column("claim", sa.Text, nullable=False),
        sa.Column("policy_class", sa.String, nullable=False), sa.Column("lifecycle_state", sa.String, nullable=False),
        sa.Column("establishment", sa.String, nullable=False), sa.Column("review", sa.String, nullable=False),
        sa.Column("correction_events", sa.JSON), sa.Column("confidence_inputs", sa.JSON),
        sa.Column("evidence_summary", sa.JSON), sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_to", sa.DateTime(timezone=True)), sa.Column("context", sa.String),
        sa.Column("exceptions", sa.JSON), sa.Column("confirmation_identity", sa.String),
        sa.Column("confirmation_time", sa.DateTime(timezone=True)), sa.Column("source_id", uuid, nullable=False),
        *common(),
    )
    sa.Table(
        "review_inbox_items", metadata, sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False), sa.Column("item_type", sa.String, nullable=False),
        sa.Column("subject_refs", sa.JSON, nullable=False), sa.Column("proposal", sa.JSON, nullable=False),
        sa.Column("risk", sa.String, nullable=False), sa.Column("evidence", sa.JSON, nullable=False),
        sa.Column("state", sa.String, nullable=False), sa.Column("resolver_id", uuid),
        sa.Column("resolved_at", sa.DateTime(timezone=True)), sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("expected_version", sa.Integer), *common(),
    )
    sa.Table(
        "asset_blobs", metadata, sa.Column("id", uuid, primary_key=True), sa.Column("owner_id", uuid, nullable=False),
        sa.Column("sha256", sa.String, nullable=False), sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("storage_backend", sa.String, nullable=False), sa.Column("storage_key", sa.String, nullable=False),
        sa.Column("reference_count", sa.Integer, nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_integrity_check_at", sa.DateTime(timezone=True)), *common(),
        sa.UniqueConstraint("sha256", "size_bytes"),
    )
    sa.Table(
        "assets", metadata, sa.Column("id", uuid, primary_key=True), sa.Column("owner_id", uuid, nullable=False),
        sa.Column("blob_id", uuid, nullable=False), sa.Column("original_name", sa.String, nullable=False),
        sa.Column("media_type", sa.String, nullable=False), sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("sha256", sa.String, nullable=False), sa.Column("storage_backend", sa.String, nullable=False),
        sa.Column("storage_key", sa.String, nullable=False), sa.Column("source_id", uuid, nullable=False),
        sa.Column("user_metadata", sa.JSON), sa.Column("capture_at", sa.DateTime(timezone=True)),
        sa.Column("location_evidence", sa.JSON), sa.Column("integrity_state", sa.String, nullable=False),
        sa.Column("processing_state", sa.String, nullable=False), sa.Column("retention", sa.String, nullable=False),
        *common(),
    )
    sa.Table(
        "derived_contents", metadata, sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False), sa.Column("target_type", sa.String, nullable=False),
        sa.Column("target_id", uuid, nullable=False), sa.Column("kind", sa.String, nullable=False),
        sa.Column("derivation_version", sa.String, nullable=False), sa.Column("generator_kind", sa.String, nullable=False),
        sa.Column("generator_version", sa.String, nullable=False), sa.Column("derived_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.String), sa.Column("confidence_inputs", sa.JSON), sa.Column("payload_ref", sa.Text),
        sa.Column("state", sa.String, nullable=False), sa.Column("sensitivity", sa.String, nullable=False),
        sa.Column("information_class", sa.String, nullable=False), sa.Column("canonicality", sa.String, nullable=False),
        sa.Column("source_kind", sa.String, nullable=False), sa.Column("source_id", uuid, nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True)), sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("lifecycle_state", sa.String, nullable=False), sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *common(), sa.UniqueConstraint("owner_id", "target_type", "target_id", "kind", "derivation_version"),
    )
    sa.Table(
        "derivation_edges", metadata, sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False), sa.Column("source_type", sa.String, nullable=False),
        sa.Column("source_id", uuid, nullable=False), sa.Column("derived_type", sa.String, nullable=False),
        sa.Column("derived_id", uuid, nullable=False), sa.Column("role", sa.String, nullable=False),
        sa.Column("contribution_weight", sa.Numeric), sa.Column("generator_version", sa.String, nullable=False),
        *common(),
    )
    sa.Table(
        "idempotency_records", metadata, sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False), sa.Column("client_id", uuid, nullable=False),
        sa.Column("operation", sa.String, nullable=False), sa.Column("idempotency_key", uuid, nullable=False),
        sa.Column("payload_digest", sa.String), sa.Column("outcome", sa.JSON),
        sa.Column("status", sa.String, nullable=False), sa.Column("tombstoned_at", sa.DateTime(timezone=True)),
        *common(), sa.UniqueConstraint("client_id", "operation", "idempotency_key"),
    )
    sa.Table(
        "jobs", metadata, sa.Column("id", uuid, primary_key=True), sa.Column("owner_id", uuid, nullable=False),
        sa.Column("client_id", uuid), sa.Column("job_type", sa.String, nullable=False),
        sa.Column("payload_ref", sa.Text, nullable=False), sa.Column("idempotency_key", uuid),
        sa.Column("state", sa.String, nullable=False), sa.Column("priority", sa.Integer, nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False), sa.Column("max_attempts", sa.Integer, nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_token", sa.Integer, nullable=False), *common(),
    )
    audit_constraints = [sa.CheckConstraint("action != 'add_expense'")] if reject_audit else []
    sa.Table(
        "audit_events", metadata, sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False), sa.Column("client_id", uuid),
        sa.Column("correlation_id", uuid, nullable=False), sa.Column("action", sa.String, nullable=False),
        sa.Column("tool", sa.String), sa.Column("effective_scope", sa.String),
        sa.Column("target_category", sa.String), sa.Column("target_id", uuid),
        sa.Column("outcome", sa.String, nullable=False), sa.Column("error_code", sa.String),
        sa.Column("duration_ms", sa.Integer, nullable=False), sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("risk", sa.String, nullable=False), sa.Column("authorization_decision", sa.String),
        *audit_constraints,
    )
    metadata.create_all(engine)
    return metadata


def _seed(factory, metadata):
    owner_id, client_id = uuid4(), uuid4()
    with factory.begin() as session:
        session.execute(metadata.tables["owners"].insert().values(id=owner_id))
        session.execute(metadata.tables["clients"].insert().values(
            id=client_id, owner_id=owner_id, status="active", permission_epoch=1,
        ))
    return owner_id, client_id


def test_canonical_expense_survives_restart_and_is_visible_to_another_process(tmp_path):
    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore

    database = tmp_path / "brain.sqlite"
    dsn = f"sqlite+pysqlite:///{database.as_posix()}"
    engine = sa.create_engine(dsn)
    metadata = _schema(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    owner_id, client_id = _seed(factory, metadata)
    store = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)
    created = store.add_expense(
        amount="10.0000", currency="CNY", category="food", description="午饭",
        occurred_timezone="Asia/Shanghai", requested_scope="finance",
        idempotency_key=uuid4(), source_text="午饭 10 CNY",
    )
    engine.dispose()

    code = (
        "import json, sqlalchemy as sa; from sqlalchemy.orm import Session, sessionmaker; "
        "from uuid import UUID; from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore; "
        f"e=sa.create_engine({dsn!r}); s=AuthoritativeStore(sessionmaker(e,class_=Session,expire_on_commit=False),"
        f"owner_id=UUID({str(owner_id)!r}),client_id=UUID({str(client_id)!r})); "
        "print(json.dumps(s.list_expenses(),default=str,ensure_ascii=False))"
    )
    observed = subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True)
    rows = json.loads(observed.stdout)
    assert rows == [{"expense_id": created["expense_id"], "amount": "10.0000", "currency": "CNY",
                     "category": "food", "description": "午饭", "source_id": created["source_id"]}]

    verify_engine = sa.create_engine(dsn)
    reflected = sa.MetaData()
    reflected.reflect(verify_engine)
    with Session(verify_engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(reflected.tables["intake_requests"])) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(reflected.tables["raw_inputs"])) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(reflected.tables["expenses"])) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(reflected.tables["idempotency_records"])) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(reflected.tables["jobs"])) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(reflected.tables["audit_events"])) == 1
    verify_engine.dispose()


def test_failed_audit_prevents_canonical_committed_and_rolls_back_all_effects(tmp_path):
    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore

    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'rollback.sqlite').as_posix()}")
    metadata = _schema(engine, reject_audit=True)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    owner_id, client_id = _seed(factory, metadata)
    store = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)
    with pytest.raises(sa.exc.IntegrityError):
        store.add_expense(
            amount="10.0000", currency="CNY", category="food", description="午饭",
            occurred_timezone="Asia/Shanghai", requested_scope="finance",
            idempotency_key=uuid4(), source_text="午饭 10 CNY",
        )
    with factory() as session:
        for name in ("intake_requests", "raw_inputs", "expenses", "idempotency_records", "jobs", "audit_events"):
            assert session.scalar(sa.select(sa.func.count()).select_from(metadata.tables[name])) == 0
    engine.dispose()


def test_all_canonical_domains_share_durable_uow_and_operation_status(tmp_path):
    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore

    database = tmp_path / "domains.sqlite"
    engine = sa.create_engine(f"sqlite+pysqlite:///{database.as_posix()}")
    metadata = _schema(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    owner_id, client_id = _seed(factory, metadata)
    store = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)
    project = store.create_project(name="Brain", purpose="durable", requested_scope="project", idempotency_key=uuid4())
    task = store.start_project_task(
        project_id=UUID(project["project_id"]), goal="收敛", revision="abc", dirty_state=False,
        constraints=["evidence"], idempotency_key=uuid4(),
    )
    checkpoint = store.checkpoint_project_task(
        task_id=UUID(task["task_id"]), completed_work="迁移", next_step="验收",
        problems="", revision="def", idempotency_key=uuid4(),
    )
    outcomes = [
        store.save_note(content="长期笔记", requested_scope="knowledge", idempotency_key=uuid4()),
        store.add_todo(content="完成迁移验证", requested_scope="todo", idempotency_key=uuid4()),
        project, task, checkpoint,
        store.propose_self_claim(category="value", claim_text="重视证据", policy_class="C", requested_scope="self", idempotency_key=uuid4()),
        store.create_review_item(item_type="profile_confirmation", subject_refs=["self"], proposal={"approve": True}, requested_scope="review", idempotency_key=uuid4()),
    ]
    restarted = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)
    assert all(outcome["persistence"] == "canonical_committed" for outcome in outcomes)
    assert restarted.get_operation_status(UUID(outcomes[-1]["operation_id"]))["status"] == "completed"
    assert restarted.list_todos()[0]["content"] == "完成迁移验证"
    assert restarted.get_project_recovery(UUID(project["project_id"]))["next_step"] == "验收"
    with factory() as session:
        for name in ("todos", "projects", "self_claims", "review_inbox_items"):
            assert session.scalar(sa.select(sa.func.count()).select_from(metadata.tables[name])) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(metadata.tables["raw_inputs"])) == 7
        assert session.scalar(sa.select(sa.func.count()).select_from(metadata.tables["jobs"])) == 7
        assert session.scalar(sa.select(sa.func.count()).select_from(metadata.tables["audit_events"])) == 7
    engine.dispose()


def test_workspace_sync_invalidates_modules_and_fresh_client_recovers(tmp_path):
    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore

    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'project.sqlite').as_posix()}")
    metadata = _schema(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    owner_id, client_id = _seed(factory, metadata)
    store = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)
    project = store.create_project(name="Brain", purpose="continuity", requested_scope="project", idempotency_key=uuid4())
    project_id = UUID(project["project_id"])
    sync_key = uuid4()
    first = store.sync_workspace(
        project_id=project_id, approved_root_identity="/approved/brain", revision="a" * 40,
        branch_ref="main", dirty_state=False, changed_paths=[], file_hashes={"apps/api.py": "1" * 64},
        modules=[{"name": "apps", "paths": ["apps"], "core_files": ["apps/api.py"],
                  "file_hashes": {"apps/api.py": "1" * 64}}], bridge_client_id="bridge-a",
        idempotency_key=sync_key,
    )
    assert first["persistence"] == "canonical_committed"
    replay = store.sync_workspace(
        project_id=project_id, approved_root_identity="/approved/brain", revision="a" * 40,
        branch_ref="main", dirty_state=False, changed_paths=[], file_hashes={"apps/api.py": "1" * 64},
        modules=[{"name": "apps", "paths": ["apps"], "core_files": ["apps/api.py"],
                  "file_hashes": {"apps/api.py": "1" * 64}}], bridge_client_id="bridge-a",
        idempotency_key=sync_key,
    )
    assert replay == first
    store.sync_workspace(
        project_id=project_id, approved_root_identity="/approved/brain", revision="b" * 40,
        branch_ref="main", dirty_state=True, changed_paths=["apps/api.py"], file_hashes={"apps/api.py": "2" * 64},
        modules=[], bridge_client_id="bridge-a", idempotency_key=uuid4(),
    )
    restarted = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)
    recovered = restarted.get_project_recovery(project_id)
    assert recovered["workspace_evidence"]["revision"] == "b" * 40
    assert recovered["workspace_evidence"]["dirty"] is True
    assert recovered["modules"][0]["freshness"] == "stale"
    assert recovered["modules"][0]["stale_reasons"]
    with pytest.raises(Exception) as caught:
        store.sync_workspace(
            project_id=project_id, approved_root_identity="/other/project", revision="c" * 40,
            branch_ref="main", dirty_state=False, changed_paths=[], file_hashes={}, modules=[],
            bridge_client_id="bridge-a", idempotency_key=uuid4(),
        )
    assert getattr(caught.value, "code", None) == "WORKSPACE_BOUNDARY_VIOLATION"


def test_project_decision_constraint_and_finalization_are_durable(tmp_path):
    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore

    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'lifecycle.sqlite').as_posix()}")
    metadata = _schema(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    owner_id, client_id = _seed(factory, metadata)
    store = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)
    project = store.create_project(name="Brain", purpose="lifecycle", requested_scope="project", idempotency_key=uuid4())
    project_id = UUID(project["project_id"])
    task = store.start_project_task(project_id=project_id, goal="ship", revision="abc", dirty_state=False,
                                    constraints=[], idempotency_key=uuid4())
    store.record_project_fact(kind="decision", project_id=project_id, statement="Use SQL",
                              rationale="durable", affected_modules=["core"], idempotency_key=uuid4())
    store.record_project_fact(kind="constraint", project_id=project_id, statement="No secrets",
                              rationale="safety", affected_modules=["core"], idempotency_key=uuid4())
    store.finalize_project_task(
        task_id=UUID(task["task_id"]), outcome="complete", verification="tests pass", remaining_work="",
        end_revision="def", end_dirty_state=False, changed_files=["core/db.py"], idempotency_key=uuid4(),
    )
    recovered = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id).get_project_recovery(project_id)
    assert recovered["active_task"] is None
    assert recovered["decisions"][0]["statement"] == "Use SQL"
    assert recovered["constraints"][0]["statement"] == "No secrets"
    assert recovered["change_events"][0]["statement"] == "complete"
    engine.dispose()


def test_review_confirmation_is_durable_owner_bound_versioned_and_single_use(tmp_path):
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore

    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'review.sqlite').as_posix()}")
    metadata = _schema(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    owner_id, client_id = _seed(factory, metadata)
    store = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)
    claim = store.propose_self_claim(
        category="value", claim_text="Evidence matters", policy_class="C",
        requested_scope="self", idempotency_key=uuid4(),
    )
    item = store.create_review_item(
        item_type="profile_confirmation", subject_refs=[claim["claim_id"]],
        proposal={"activate": claim["claim_id"]}, requested_scope="review", idempotency_key=uuid4(),
    )
    item_id = UUID(item["review_item_id"])
    resolution_key = uuid4()
    with pytest.raises(BrainError) as caught:
        store.resolve_review_item(item_id=item_id, expected_version=2, decision="approved",
                                  idempotency_key=uuid4())
    assert caught.value.code == "VERSION_CONFLICT"
    result = store.resolve_review_item(item_id=item_id, expected_version=1, decision="approved",
                                       idempotency_key=resolution_key)
    assert store.resolve_review_item(item_id=item_id, expected_version=1, decision="approved",
                                     idempotency_key=resolution_key) == result
    restarted = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)
    assert restarted.list_review_items(state="approved")[0]["review_item_id"] == str(item_id)
    with factory() as session:
        row = session.execute(sa.select(metadata.tables["self_claims"])).mappings().one()
        assert row["lifecycle_state"] == "active" and row["confirmation_identity"] == str(owner_id)
    with pytest.raises(BrainError) as caught:
        restarted.resolve_review_item(item_id=item_id, expected_version=1, decision="rejected",
                                      idempotency_key=uuid4())
    assert caught.value.code == "CONFIRMATION_REQUIRED"
    engine.dispose()


def test_structured_reads_and_todo_completion_are_durable_and_exact(tmp_path):
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore

    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'structured.sqlite').as_posix()}")
    metadata = _schema(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    owner_id, client_id = _seed(factory, metadata)
    store = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)
    todo = store.add_todo(content="finish", requested_scope="todo", idempotency_key=uuid4())
    store.add_expense(amount="12.5000", currency="CNY", category="food", description="meal",
                      occurred_timezone="Asia/Shanghai", requested_scope="finance",
                      idempotency_key=uuid4(), source_text="meal")
    store.add_expense(amount="2.0000", currency="USD", category="tool", description="service",
                      occurred_timezone="UTC", requested_scope="finance",
                      idempotency_key=uuid4(), source_text="service")
    outcome = store.complete_todo(todo_id=UUID(todo["todo_id"]), expected_version=1,
                                  idempotency_key=uuid4())
    assert outcome["todo_id"] == todo["todo_id"]
    assert AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id).list_todos()[0]["state"] == "completed"
    summary = store.get_expense_summary()
    assert summary == {"totals": [
        {"currency": "CNY", "amount": "12.5000", "record_count": 1},
        {"currency": "USD", "amount": "2.0000", "record_count": 1},
    ], "conversion_applied": False}
    with pytest.raises(BrainError) as caught:
        store.complete_todo(todo_id=UUID(todo["todo_id"]), expected_version=1,
                            idempotency_key=uuid4())
    assert caught.value.code == "VERSION_CONFLICT"
    engine.dispose()


def test_asset_bytes_metadata_dedupe_and_job_are_persisted_together(tmp_path):
    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore
    from personal_brain_infra.storage.local import LocalStorage

    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'assets.sqlite').as_posix()}")
    metadata = _schema(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    owner_id, client_id = _seed(factory, metadata)
    store = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)
    source = store.save_note(content="asset source", requested_scope="knowledge", idempotency_key=uuid4())
    storage = LocalStorage(tmp_path / "blobs")
    first = store.upload_asset(
        content=b"same bytes", original_name="one.txt", media_type="text/plain",
        source_id=UUID(source["record_id"]), idempotency_key=uuid4(), storage=storage,
    )
    second = store.upload_asset(
        content=b"same bytes", original_name="two.txt", media_type="text/plain",
        source_id=UUID(source["record_id"]), idempotency_key=uuid4(), storage=storage,
    )
    assert first["blob_id"] == second["blob_id"] and second["deduplicated"] is True
    assert storage.read(first["storage_key"]) == b"same bytes"
    assert LocalStorage(tmp_path / "blobs").read(first["storage_key"]) == b"same bytes"
    with factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(metadata.tables["asset_blobs"])) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(metadata.tables["assets"])) == 2
        assert session.scalar(sa.select(metadata.tables["asset_blobs"].c.reference_count)) == 2
        assert session.scalar(sa.select(sa.func.count()).select_from(metadata.tables["jobs"]).where(
            metadata.tables["jobs"].c.job_type == "parse_asset",
        )) == 2

    from personal_brain_infra.assets.derivation import AssetDerivationService

    derivations = AssetDerivationService(factory, metadata.tables, owner_id=owner_id, storage=storage)
    parsed = derivations.process(
        asset_id=UUID(first["asset_id"]), kind="extracted_text", generator_kind="parser",
        generator_version="parser-v1", transform=lambda original: original.upper(),
    )
    replay = derivations.process(
        asset_id=UUID(first["asset_id"]), kind="extracted_text", generator_kind="parser",
        generator_version="parser-v1", transform=lambda original: original.upper(),
    )
    reprocessed = derivations.process(
        asset_id=UUID(first["asset_id"]), kind="extracted_text", generator_kind="parser",
        generator_version="parser-v2", transform=lambda original: original[::-1],
    )
    assert storage.read(parsed["payload_ref"]) == b"SAME BYTES"
    assert replay["replayed"] is True and replay["derived_id"] == parsed["derived_id"]
    assert reprocessed["derived_id"] != parsed["derived_id"]
    with factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(metadata.tables["derived_contents"])) == 2
        assert session.scalar(sa.select(sa.func.count()).select_from(metadata.tables["derivation_edges"])) == 2
    from personal_brain_worker.asset_jobs import handle_describe, handle_embed, handle_parse, handle_transcribe
    for handler, label in (
        (handle_parse, "parser"), (handle_transcribe, "transcriber"),
        (handle_describe, "describer"), (handle_embed, "embedder"),
    ):
        kwargs = {label: lambda original, marker=label: marker.encode() + b":" + original}
        outcome = handler(
            job_id=f"job-{label}", asset_id=UUID(second["asset_id"]),
            generator_version=f"{label}-v1", service=derivations, **kwargs,
        )
        assert storage.read(outcome.result_ref).startswith(label.encode())
    engine.dispose()
