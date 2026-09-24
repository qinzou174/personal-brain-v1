"""T180: governed deletion is persisted, owner-confirmed, and executes the
dependency plan across originals/derived/indexes/relations/evidence/caches."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from personal_brain_domain.common.errors import BrainError


def _schema(engine):
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
        "review_inbox_items", metadata, sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False), sa.Column("item_type", sa.String, nullable=False),
        sa.Column("subject_refs", sa.JSON, nullable=False), sa.Column("proposal", sa.JSON, nullable=False),
        sa.Column("risk", sa.String, nullable=False), sa.Column("evidence", sa.JSON, nullable=False),
        sa.Column("state", sa.String, nullable=False), sa.Column("resolver_id", uuid),
        sa.Column("resolved_at", sa.DateTime(timezone=True)), sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("expected_version", sa.Integer), *common(),
    )
    sa.Table(
        "deletion_plans", metadata, sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("requested_targets", sa.JSON, nullable=False),
        sa.Column("impact_graph", sa.JSON, nullable=False),
        sa.Column("policy_actions", sa.JSON, nullable=False),
        sa.Column("backup_implications", sa.JSON),
        sa.Column("risk", sa.String, nullable=False),
        sa.Column("confirmation_state", sa.String, nullable=False),
        sa.Column("confirmation_identity", sa.String),
        sa.Column("confirmation_time", sa.DateTime(timezone=True)),
        sa.Column("execution_state", sa.String, nullable=False),
        sa.Column("reconciliation_state", sa.String, nullable=False),
        sa.Column("audit_ref", sa.String), *common(),
    )
    sa.Table(
        "deletion_actions", metadata, sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False), sa.Column("plan_id", uuid, nullable=False),
        sa.Column("target_type", sa.String, nullable=False), sa.Column("target_id", uuid, nullable=False),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("produced_purged", sa.Boolean, nullable=False),
        sa.Column("backup_purge_due", sa.Boolean, nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True)),
        sa.Column("opaque_deletion_version", sa.BigInteger, nullable=False), *common(),
    )
    sa.Table(
        "evidence", metadata, sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False), sa.Column("target_type", sa.String, nullable=False),
        sa.Column("target_id", uuid, nullable=False), sa.Column("source_type", sa.String, nullable=False),
        sa.Column("source_id", uuid, nullable=False), sa.Column("stance", sa.String, nullable=False),
        sa.Column("source_trust", sa.String, nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("context", sa.String), sa.Column("contribution", sa.Numeric),
        sa.Column("lifecycle_state", sa.String, nullable=False), *common(),
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
        *common(),
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
        "search_index_entries", metadata, sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False), sa.Column("target_type", sa.String, nullable=False),
        sa.Column("target_id", uuid, nullable=False), sa.Column("authorized_scope", sa.String, nullable=False),
        sa.Column("sensitivity", sa.String, nullable=False), sa.Column("canonicality", sa.String, nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True)), sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("freshness", sa.String, nullable=False), sa.Column("searchable_text", sa.Text),
        sa.Column("vector_model_version", sa.String), sa.Column("metadata_filters", sa.JSON),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False), *common(),
    )
    sa.Table(
        "conflicts", metadata, sa.Column("id", uuid, primary_key=True), sa.Column("owner_id", uuid, nullable=False),
        sa.Column("participants", sa.JSON, nullable=False), sa.Column("conflict_type", sa.String, nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False), sa.Column("evidence", sa.JSON),
        sa.Column("state", sa.String, nullable=False), sa.Column("resolution", sa.JSON),
        sa.Column("resolver", sa.String), *common(),
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
    sa.Table(
        "audit_events", metadata, sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False), sa.Column("client_id", uuid),
        sa.Column("correlation_id", uuid, nullable=False), sa.Column("action", sa.String, nullable=False),
        sa.Column("tool", sa.String), sa.Column("effective_scope", sa.String),
        sa.Column("target_category", sa.String), sa.Column("target_id", uuid),
        sa.Column("outcome", sa.String, nullable=False), sa.Column("error_code", sa.String),
        sa.Column("duration_ms", sa.Integer, nullable=False), sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("risk", sa.String, nullable=False), sa.Column("authorization_decision", sa.String),
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


def test_deletion_plan_preview_is_persisted_and_review_gated(tmp_path):
    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore

    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'plan.sqlite').as_posix()}")
    metadata = _schema(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    owner_id, client_id = _seed(factory, metadata)
    store = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)

    expense = store.add_expense(
        amount="9.9000", currency="CNY", category="food", description="午餐",
        occurred_timezone="Asia/Shanghai", requested_scope="finance",
        idempotency_key=uuid4(), source_text="午餐 9.9 CNY",
    )
    target = ("expense", UUID(expense["expense_id"]))
    plan = store.create_deletion_plan(
        targets=[target], dependents={target[1]: [("derived_content", uuid4()), ("relation", uuid4())]},
        requested_scope="finance", idempotency_key=uuid4(),
    )
    # Preview persists; nothing is hidden or purged before confirmation.
    restarted = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)
    preview = restarted.get_deletion_plan(UUID(plan["plan_id"]))
    assert preview["execution_state"] == "preview"
    assert preview["confirmation_state"] == "pending"
    assert preview["review_item_id"]
    assert restarted.list_expenses()[0]["expense_id"] == expense["expense_id"]


def test_rejected_deletion_plan_changes_nothing(tmp_path):
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore

    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'reject.sqlite').as_posix()}")
    metadata = _schema(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    owner_id, client_id = _seed(factory, metadata)
    store = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)
    outcome = store.add_todo(content="keep", requested_scope="todo", idempotency_key=uuid4())
    plan = store.create_deletion_plan(
        targets=[("todo", UUID(outcome["todo_id"]))], dependents={}, requested_scope="todo",
        idempotency_key=uuid4(),
    )
    store.resolve_review_item(
        item_id=UUID(plan["review_item_id"]), expected_version=1, decision="rejected",
        idempotency_key=uuid4(),
    )
    restarted = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)
    assert restarted.list_todos()[0]["todo_id"] == outcome["todo_id"]
    assert restarted.get_deletion_plan(UUID(plan["plan_id"]))["confirmation_state"] == "rejected"


def test_approved_deletion_executes_dependency_plan_and_enqueues_reconciliation(tmp_path):
    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore

    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'execute.sqlite').as_posix()}")
    metadata = _schema(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    owner_id, client_id = _seed(factory, metadata)
    store = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)

    expense = store.add_expense(
        amount="5.0000", currency="CNY", category="food", description="咖啡",
        occurred_timezone="Asia/Shanghai", requested_scope="finance",
        idempotency_key=uuid4(), source_text="咖啡 5 CNY",
    )
    expense_id = UUID(expense["expense_id"])
    derived_id, evidence_id, search_entry_id, relation_id = uuid4(), uuid4(), uuid4(), uuid4()

    def open_dependencies(session: Session) -> None:
        session.execute(metadata.tables["derived_contents"].insert().values(
            id=derived_id, owner_id=owner_id, target_type="expense", target_id=expense_id,
            kind="summary", derivation_version="v1", generator_kind="summarizer",
            generator_version="s-v1", derived_at=datetime.now(timezone.utc), confidence=None,
            confidence_inputs=None, payload_ref=None, state="active", sensitivity="normal",
            information_class="ai_extraction", canonicality="derived", source_kind="ai_extraction",
            source_id=expense_id, valid_from=None, valid_to=None, lifecycle_state="active", deleted_at=None,
        ))
        session.execute(metadata.tables["derivation_edges"].insert().values(
            id=uuid4(), owner_id=owner_id, source_type="expense", source_id=expense_id,
            derived_type="derived_content", derived_id=derived_id, role="summarized_from",
            contribution_weight=None, generator_version="s-v1",
        ))
        session.execute(metadata.tables["evidence"].insert().values(
            id=evidence_id, owner_id=owner_id, target_type="self_claim", target_id=uuid4(),
            source_type="expense", source_id=expense_id, stance="supports", source_trust="explicit_user_statement",
            observed_at=datetime.now(timezone.utc), context=None, contribution=None, lifecycle_state="active",
        ))
        session.execute(metadata.tables["search_index_entries"].insert().values(
            id=search_entry_id, owner_id=owner_id, target_type="expense", target_id=expense_id,
            authorized_scope="finance", sensitivity="normal", canonicality="canonical",
            valid_from=None, valid_to=None, freshness="fresh", searchable_text="咖啡",
            vector_model_version=None, metadata_filters=None, indexed_at=datetime.now(timezone.utc),
        ))
        session.execute(metadata.tables["conflicts"].insert().values(
            id=uuid4(), owner_id=owner_id, participants=[str(expense_id)], conflict_type="depends",
            detected_at=datetime.now(timezone.utc), evidence=[], state="open", resolution=None, resolver=None,
        ))
        session.execute(metadata.tables["raw_inputs"].insert().values(
            id=expense_id, owner_id=owner_id, intake_request_id=uuid4(), client_id=client_id,
            content_text="咖啡", asset_ref=None, content_hash="h", original_at=datetime.now(timezone.utc),
            original_timezone="Asia/Shanghai", source_channel="api", language="zh-CN",
            retention_policy="canonical", sensitivity="normal", information_class="explicit_user_statement",
            canonicality="canonical", source_kind="explicit_user_statement", source_id=expense_id,
            valid_from=None, valid_to=None, lifecycle_state="active", deleted_at=None,
        ))

    with factory.begin() as session:
        open_dependencies(session)

    plan = store.create_deletion_plan(
        targets=[("expense", expense_id)],
        dependents={expense_id: [("derived_content", derived_id), ("evidence", evidence_id),
                                 ("search_index", search_entry_id), ("relation", relation_id)]},
        requested_scope="finance", idempotency_key=uuid4(),
    )
    item_id = UUID(plan["review_item_id"])
    # Stale version never executes.
    with pytest.raises(BrainError) as caught:
        store.resolve_review_item(item_id=item_id, expected_version=0, decision="approved",
                                  idempotency_key=uuid4())
    assert caught.value.code == "VERSION_CONFLICT"
    result = store.resolve_review_item(item_id=item_id, expected_version=1, decision="approved",
                                       idempotency_key=uuid4())

    # Rejected/expired guard: second consume impossible.
    with pytest.raises(BrainError) as caught:
        store.resolve_review_item(item_id=item_id, expected_version=1, decision="approved",
                                  idempotency_key=uuid4())
    assert caught.value.code == "CONFIRMATION_REQUIRED"

    restarted = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)
    plan_state = restarted.get_deletion_plan(UUID(plan["plan_id"]))
    assert plan_state["execution_state"] == "completed"
    assert plan_state["reconciliation_state"] == "queued"
    assert plan_state["confirmation_state"] == "confirmed"
    with factory() as session:
        actions = session.execute(sa.select(metadata.tables["deletion_actions"])).mappings().all()
        assert len(actions) == 5
        assert {row["target_type"] for row in actions} == {"expense", "derived_content", "evidence", "search_index", "relation"}
        # Original is tombstoned (not hard-deleted) and body-free audit recorded.
        raw_row = session.execute(sa.select(metadata.tables["raw_inputs"]).where(
            metadata.tables["raw_inputs"].c.id == expense_id,
        )).mappings().one()
        assert raw_row["lifecycle_state"] == "deleted"
        # Evidence recalculated: evidence row detached from the deleted source.
        ev_rows = session.execute(sa.select(metadata.tables["evidence"])).mappings().all()
        assert all(row["lifecycle_state"] == "recomputing" for row in ev_rows)
        # Fenced reconciliation job enqueued.
        job = session.execute(sa.select(metadata.tables["jobs"]).where(
            metadata.tables["jobs"].c.job_type == "reconcile_deletion",
        )).mappings().one()
        assert job["state"] in {"queued", "leased"}
        # Audit outcome recorded body-free.
        audit = session.execute(sa.select(metadata.tables["audit_events"]).where(
            metadata.tables["audit_events"].c.action == "resolve_review_item",
        ).order_by(metadata.tables["audit_events"].c.occurred_at.desc())).mappings().first()
        assert audit["outcome"] == "approved"
    assert result["persistence"] == "canonical_committed"
    engine.dispose()


def test_reconciliation_job_cleans_search_and_derived_dependents(tmp_path):
    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore

    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'reconcile.sqlite').as_posix()}")
    metadata = _schema(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    owner_id, client_id = _seed(factory, metadata)
    store = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)
    expense = store.add_expense(
        amount="3.0000", currency="CNY", category="food", description="水",
        occurred_timezone="Asia/Shanghai", requested_scope="finance",
        idempotency_key=uuid4(), source_text="水 3 CNY",
    )
    expense_id = UUID(expense["expense_id"])
    derived_id = uuid4()
    with factory.begin() as session:
        session.execute(metadata.tables["derived_contents"].insert().values(
            id=derived_id, owner_id=owner_id, target_type="expense", target_id=expense_id,
            kind="summary", derivation_version="v1", generator_kind="summarizer",
            generator_version="s-v1", derived_at=datetime.now(timezone.utc), confidence=None,
            confidence_inputs=None, payload_ref=None, state="active", sensitivity="normal",
            information_class="ai_extraction", canonicality="derived", source_kind="ai_extraction",
            source_id=expense_id, valid_from=None, valid_to=None, lifecycle_state="active", deleted_at=None,
        ))
        session.execute(metadata.tables["search_index_entries"].insert().values(
            id=uuid4(), owner_id=owner_id, target_type="expense", target_id=expense_id,
            authorized_scope="finance", sensitivity="normal", canonicality="canonical",
            valid_from=None, valid_to=None, freshness="fresh", searchable_text="水",
            vector_model_version=None, metadata_filters=None, indexed_at=datetime.now(timezone.utc),
        ))
        session.execute(metadata.tables["raw_inputs"].insert().values(
            id=expense_id, owner_id=owner_id, intake_request_id=uuid4(), client_id=client_id,
            content_text="水", asset_ref=None, content_hash="h", original_at=datetime.now(timezone.utc),
            original_timezone="Asia/Shanghai", source_channel="api", language="zh-CN",
            retention_policy="canonical", sensitivity="normal", information_class="explicit_user_statement",
            canonicality="canonical", source_kind="explicit_user_statement", source_id=expense_id,
            valid_from=None, valid_to=None, lifecycle_state="active", deleted_at=None,
        ))
    plan = store.create_deletion_plan(
        targets=[("expense", expense_id)],
        dependents={expense_id: [("derived_content", derived_id), ("search_index", uuid4())]},
        requested_scope="finance", idempotency_key=uuid4(),
    )
    store.resolve_review_item(item_id=UUID(plan["review_item_id"]), expected_version=1,
                              decision="approved", idempotency_key=uuid4())

    # Run the durable reconcile_deletion handler with fencing.
    import personal_brain_worker.job_handlers as handlers_mod

    with factory.begin() as session:
        job = session.execute(sa.select(metadata.tables["jobs"]).where(
            metadata.tables["jobs"].c.job_type == "reconcile_deletion",
        )).mappings().one()
        session.execute(metadata.tables["jobs"].update().where(
            metadata.tables["jobs"].c.id == job["id"],
        ).values(state="leased", claim_token=2))
        claim_token = 2

    class FakeContext:
        def progress(self, percent, note=None):
            pass

    pending_table = metadata  # noqa: F841
    dict_job = dict(job)
    # Execute handler against the same binding factory, not a stub.
    module_handlers = handlers_mod.build_job_handlers(factory, metadata.tables, storage=None)
    outcome = module_handlers["reconcile_deletion"](dict_job, FakeContext())
    assert outcome["removed_search"] == 1
    assert outcome["removed_derived"] == 1
    with factory() as session:
        remaining_search = session.scalar(sa.select(sa.func.count()).select_from(
            metadata.tables["search_index_entries"]))
        assert remaining_search == 0
        plan_row = session.execute(sa.select(metadata.tables["deletion_plans"])).mappings().one()
        assert plan_row["reconciliation_state"] == "completed"
    engine.dispose()


def test_conflict_and_retention_workflows_persist_domain_decisions(tmp_path):
    from personal_brain_domain.memory.conflicts import resolve_conflict
    from personal_brain_domain.operations.retention import apply_retention
    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore

    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'conflict.sqlite').as_posix()}")
    metadata = _schema(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    owner_id, client_id = _seed(factory, metadata)
    store = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)

    conflict = resolve_conflict(participants=("a", "b"), mode="time")
    assert set(conflict.participants) == {"a", "b"}
    persisted = store.persist_conflict(
        participants=["a", "b"], conflict_type="temporal", state=conflict.state,
        idempotency_key=uuid4(), requested_scope="review",
    )
    restarted = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)
    assert restarted.list_conflicts()[0]["state"] == conflict.state

    retention = apply_retention(kind="candidate", age_days=95)
    assert retention.action == "archive"
    applied = store.persist_retention(
        target_type="memory", target_id=uuid4(), action=retention.action,
        idempotency_key=uuid4(), requested_scope="review",
    )
    assert applied["persistence"] == "canonical_committed"
    engine.dispose()