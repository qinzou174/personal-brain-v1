"""Life records: Document, Expense, Todo, Event, Experience, Entity and Relation.

RawInput/IntakeRequest already exist in 0001; this revision adds the structured
life-record tables and never recreates foundation tables. ER-04 fixes
numeric(20,4) money, mandatory currency, typed refund/adjustment kinds, todo
state transitions, acyclic event parents and same-owner relation endpoints.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0002_life_records"
down_revision = "0001_authority_core"
branch_labels = None
depends_on = None

SOURCE_VERSION = "0001_authority_core"
TARGET_VERSION = revision
AFFECTED_CANONICAL = ("Document", "Expense", "Todo", "Event", "Experience", "Entity", "Relation")
AFFECTED_DERIVED = ()
LOCK_STORAGE_IMPACT = "Adds 7 empty canonical life-record tables and indexes; no existing rows rewritten."
BACKUP_PREREQUISITE = "Empty synthetic database only; any populated target requires an independently verified restore point before migration."
RESTORE_STRATEGY = "Production rollback is restore from the verified pre-migration backup; downgrade is restricted to isolated brain_migration_test_* schemas."
PREFLIGHT_SQL = "SELECT to_regclass('raw_inputs') IS NOT NULL AS core_exists"

CREATED_TABLES = (
    "documents", "expenses", "todos", "events", "experiences", "entities", "relations",
)
POST_VALIDATION_SQL = (
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = current_schema() "
    "AND table_name IN (" + ",".join("'" + name + "'" for name in CREATED_TABLES) + ")"
)

SENSITIVITY = "'normal','personal','private','highly_private'"
INFORMATION_CLASS = "'fact','explicit_user_statement','observation','ai_extraction','ai_inference'"
SOURCE_KIND = "'explicit_user_statement','original_document','system_fact','observation','ai_extraction','ai_inference'"


def _id():
    return sa.Column("id", UUID(as_uuid=True), primary_key=True)


def _owner():
    return sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("owners.id", ondelete="RESTRICT"), nullable=False)


def _source():
    return sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("raw_inputs.id", ondelete="RESTRICT"), nullable=False)


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def _version():
    return sa.Column("version", sa.Integer(), nullable=False, server_default="1")


def _information():
    return (
        sa.Column("sensitivity", sa.String(32), nullable=False),
        sa.Column("information_class", sa.String(32), nullable=False),
        sa.Column("canonicality", sa.String(16), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("lifecycle_state", sa.String(32), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(f"sensitivity IN ({SENSITIVITY})", name="sensitivity_allowed"),
        sa.CheckConstraint(f"information_class IN ({INFORMATION_CLASS})", name="information_class_allowed"),
        sa.CheckConstraint(f"source_kind IN ({SOURCE_KIND})", name="source_kind_allowed"),
        sa.CheckConstraint("valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from", name="valid_interval_order"),
    )


def upgrade() -> None:
    op.create_table(
        "documents", _id(), _owner(),
        sa.Column("raw_input_id", UUID(as_uuid=True), sa.ForeignKey("raw_inputs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("asset_id", UUID(as_uuid=True)),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("document_type", sa.String(64), nullable=False),
        sa.Column("canonical_text", sa.Text()),
        sa.Column("content_ref", sa.Text()),
        sa.Column("source_metadata", JSONB),
        sa.Column("current_extraction_id", UUID(as_uuid=True)),
        sa.Column("retention", sa.String(32), nullable=False),
        *_timestamps(), _version(),
        sa.CheckConstraint("length(title) <= 512", name="document_title_bound"),
        sa.CheckConstraint("canonical_text IS NOT NULL OR content_ref IS NOT NULL", name="document_content_present"),
    )
    op.create_table(
        "expenses", _id(), _owner(),
        sa.Column("amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("description", sa.String(512), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("occurred_timezone", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("event_id", UUID(as_uuid=True)),
        _source(),
        *_information(), *_timestamps(), _version(),
        sa.CheckConstraint("amount > 0", name="expense_amount_positive"),
        sa.CheckConstraint("kind IN ('expense','refund','adjustment')", name="expense_kind_allowed"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="expense_currency_iso"),
        sa.CheckConstraint("canonicality = 'canonical'", name="expense_canonical_only"),
    )
    op.create_table(
        "todos", _id(), _owner(),
        sa.Column("content", sa.String(1024), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("due_timezone", sa.String(64)),
        sa.Column("due_window_start", sa.DateTime(timezone=True)),
        sa.Column("due_window_end", sa.DateTime(timezone=True)),
        sa.Column("due_precision", sa.String(16)),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        _source(),
        *_information(),
        sa.CheckConstraint("state IN ('pending','in_progress','completed','cancelled')", name="todo_state_allowed"),
        sa.CheckConstraint("priority BETWEEN 0 AND 9", name="todo_priority_bound"),
        sa.CheckConstraint("due_window_end IS NULL OR due_window_start IS NOT NULL", name="todo_window_order"),
        sa.CheckConstraint("due_window_end IS NULL OR due_window_end > due_window_start", name="todo_window_interval"),
    )
    op.create_table(
        "events", _id(), _owner(),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("objective_description", sa.Text(), nullable=False),
        sa.Column("subjective_experience_id", UUID(as_uuid=True)),
        sa.Column("start_at", sa.DateTime(timezone=True)),
        sa.Column("end_at", sa.DateTime(timezone=True)),
        sa.Column("event_timezone", sa.String(64), nullable=False),
        sa.Column("importance", sa.String(16), nullable=False),
        sa.Column("confidence", sa.String(32)),
        sa.Column("parent_event_id", UUID(as_uuid=True)),
        _source(),
        *_information(), _version(),
        sa.CheckConstraint("importance IN ('low','normal','high','critical')", name="event_importance_allowed"),
        sa.CheckConstraint("end_at IS NULL OR start_at IS NULL OR end_at >= start_at", name="event_time_order"),
    )
    op.create_table(
        "experiences", _id(), _owner(),
        sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_expression", sa.Text(), nullable=False),
        sa.Column("normalized_interpretation", sa.Text()),
        sa.Column("context", sa.String(256), nullable=False),
        _source(),
        sa.Column("confidence", sa.String(32)),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("sensitivity", sa.String(32), nullable=False),
        sa.Column("information_class", sa.String(32), nullable=False),
        sa.Column("canonicality", sa.String(16), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("lifecycle_state", sa.String(32), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(), _version(),
        sa.CheckConstraint("canonicality = 'canonical'", name="experience_canonical_only"),
        sa.CheckConstraint("sensitivity IN ('normal','personal','private','highly_private')", name="experience_sensitivity_allowed"),
        sa.CheckConstraint("information_class IN ('fact','explicit_user_statement','observation','ai_extraction','ai_inference')", name="experience_information_class_allowed"),
        sa.CheckConstraint("source_kind IN ('explicit_user_statement','original_document','system_fact','observation','ai_extraction','ai_inference')", name="experience_source_kind_allowed"),
    )
    op.create_table(
        "entities", _id(), _owner(),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("canonical_name", sa.String(512), nullable=False),
        sa.Column("aliases", JSONB, nullable=False),
        sa.Column("confidence", sa.String(32)),
        _source(),
        *_information(), _version(),
        sa.CheckConstraint("entity_type IN ('person','place','project','concept','media','device','organization','extensible')", name="entity_type_allowed"),
        sa.CheckConstraint("length(canonical_name) <= 512", name="entity_name_bound"),
    )
    op.create_table(
        "relations", _id(), _owner(),
        sa.Column("subject_type", sa.String(64), nullable=False),
        sa.Column("subject_id", UUID(as_uuid=True), nullable=False),
        sa.Column("predicate", sa.String(128), nullable=False),
        sa.Column("object_type", sa.String(64), nullable=False),
        sa.Column("object_id", UUID(as_uuid=True), nullable=False),
        sa.Column("confidence", sa.String(32)),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        _source(),
        sa.Column("sensitivity", sa.String(32), nullable=False),
        sa.Column("information_class", sa.String(32), nullable=False),
        sa.Column("canonicality", sa.String(16), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("lifecycle_state", sa.String(32), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(), _version(),
        sa.CheckConstraint("canonicality = 'canonical'", name="relation_canonical_only"),
        sa.CheckConstraint("sensitivity IN ('normal','personal','private','highly_private')", name="relation_sensitivity_allowed"),
        sa.CheckConstraint("information_class IN ('fact','explicit_user_statement','observation','ai_extraction','ai_inference')", name="relation_information_class_allowed"),
        sa.CheckConstraint("source_kind IN ('explicit_user_statement','original_document','system_fact','observation','ai_extraction','ai_inference')", name="relation_source_kind_allowed"),
    )
    op.create_index("ix_expenses_owner_period", "expenses", ["owner_id", "occurred_at"])
    op.create_index("ix_todos_owner_state", "todos", ["owner_id", "state"])
    op.create_index("ix_events_parent", "events", ["owner_id", "parent_event_id"])
    op.create_index("ix_relations_endpoints", "relations", ["owner_id", "subject_type", "subject_id"])
    op.create_index("ix_relations_object", "relations", ["owner_id", "object_type", "object_id"])


def downgrade() -> None:
    schema = op.get_bind().scalar(sa.text("SELECT current_schema()"))
    if not isinstance(schema, str) or not schema.startswith("brain_migration_test_"):
        raise RuntimeError("downgrade is limited to isolated synthetic test schemas; restore production from verified backup")
    for table in reversed(CREATED_TABLES):
        op.drop_table(table)
