"""ContextRequest and ContextPackage mappings; reuse SearchIndexEntry.

Only ContextRequest and ContextPackage are created here; parent revision is
0006_assets_search (search index already exists).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0007_retrieval_context"
down_revision = "0006_assets_search"
branch_labels = None
depends_on = None

SOURCE_VERSION = "0006_assets_search"
TARGET_VERSION = revision
AFFECTED_CANONICAL = ("ContextRequest", "ContextPackage")
AFFECTED_DERIVED = ()
LOCK_STORAGE_IMPACT = "Adds 2 empty context tables; no rows rewritten."
BACKUP_PREREQUISITE = "Empty synthetic database only; any populated target requires an independently verified restore point before migration."
RESTORE_STRATEGY = "Production rollback is restore from the verified pre-migration backup; downgrade is restricted to isolated brain_migration_test_* schemas."
PREFLIGHT_SQL = "SELECT to_regclass('search_index_entries') IS NOT NULL AS core_exists"

CREATED_TABLES = ("context_requests", "context_packages")
POST_VALIDATION_SQL = (
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = current_schema() "
    "AND table_name IN (" + ",".join("'" + name + "'" for name in CREATED_TABLES) + ")"
)


def _id():
    return sa.Column("id", UUID(as_uuid=True), primary_key=True)


def _owner():
    return sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("owners.id", ondelete="RESTRICT"), nullable=False)


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def upgrade() -> None:
    op.create_table(
        "context_requests", _id(), _owner(),
        sa.Column("client_id", UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("intent", sa.String(128), nullable=False),
        sa.Column("requested_scopes", JSONB, nullable=False),
        sa.Column("effective_scopes", JSONB, nullable=False),
        sa.Column("detail_level", sa.String(16), nullable=False),
        sa.Column("token_budget", sa.Integer()),
        sa.Column("size_budget", sa.Integer()),
        sa.Column("query", sa.String(8000)),
        sa.Column("target_project_id", UUID(as_uuid=True)),
        sa.Column("target_module_id", UUID(as_uuid=True)),
        sa.Column("time_start", sa.DateTime(timezone=True)),
        sa.Column("time_end", sa.DateTime(timezone=True)),
        sa.Column("correlation_id", UUID(as_uuid=True), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("detail_level IN ('summary','normal','deep')", name="context_detail_allowed"),
        sa.CheckConstraint("query IS NULL OR length(query) <= 8000", name="context_query_bound"),
    )
    op.create_table(
        "context_packages", _id(), _owner(),
        sa.Column("request_id", UUID(as_uuid=True), sa.ForeignKey("context_requests.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("intent", sa.String(128), nullable=False),
        sa.Column("current_state", JSONB),
        sa.Column("historical_rationale", JSONB),
        sa.Column("active_task", JSONB),
        sa.Column("relevant_objects", JSONB),
        sa.Column("decisions", JSONB),
        sa.Column("constraints", JSONB),
        sa.Column("recent_changes", JSONB),
        sa.Column("warnings", JSONB),
        sa.Column("suggested_next_actions", JSONB),
        sa.Column("source_references", JSONB),
        sa.Column("used_budget", sa.Integer()),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
    )


def downgrade() -> None:
    schema = op.get_bind().scalar(sa.text("SELECT current_schema()"))
    if not isinstance(schema, str) or not schema.startswith("brain_migration_test_"):
        raise RuntimeError("downgrade is limited to isolated synthetic test schemas; restore production from verified backup")
    for table in reversed(CREATED_TABLES):
        op.drop_table(table)