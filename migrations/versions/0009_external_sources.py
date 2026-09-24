"""ExternalSource and ImportCheckpoint mappings; bounded identity/conflict/checkpoint.

Reuses canonical intake; created once.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0009_external_sources"
down_revision = "0008_lifecycle_deletion"
branch_labels = None
depends_on = None

SOURCE_VERSION = "0008_lifecycle_deletion"
TARGET_VERSION = revision
AFFECTED_CANONICAL = ("ExternalSource", "ImportCheckpoint")
AFFECTED_DERIVED = ()
LOCK_STORAGE_IMPACT = "Adds 2 empty canonical external-source tables; no rows rewritten."
BACKUP_PREREQUISITE = "Empty synthetic database only; any populated target requires an independently verified restore point before migration."
RESTORE_STRATEGY = "Production rollback is restore from the verified pre-migration backup; downgrade is restricted to isolated brain_migration_test_* schemas."
PREFLIGHT_SQL = "SELECT to_regclass('raw_inputs') IS NOT NULL AS core_exists"

CREATED_TABLES = ("external_sources", "import_checkpoints")
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
        "external_sources", _id(), _owner(),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("external_identity", sa.String(256), nullable=False),
        sa.Column("display_name", sa.String(256)),
        sa.Column("endpoint", sa.String(512)),
        sa.Column("import_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("health_state", sa.String(16), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("source_kind IN ('trilium','gitea','other')", name="external_source_kind_allowed"),
        sa.CheckConstraint("health_state IN ('healthy','degraded','failed','unknown')", name="external_health_allowed"),
        sa.UniqueConstraint("owner_id", "source_kind", "external_identity", name="uq_external_source_identity"),
    )
    op.create_table(
        "import_checkpoints", _id(), _owner(),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("external_sources.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_revision", sa.String(128), nullable=False),
        sa.Column("last_imported_id", sa.String(256)),
        sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_status", sa.String(16), nullable=False),
        sa.Column("last_error", sa.String(512)),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("last_status IN ('succeeded','partial','failed','skipped')", name="import_status_allowed"),
    )
    op.create_index("ix_import_checkpoints_source", "import_checkpoints", ["owner_id", "source_id", "source_revision"])


def downgrade() -> None:
    schema = op.get_bind().scalar(sa.text("SELECT current_schema()"))
    if not isinstance(schema, str) or not schema.startswith("brain_migration_test_"):
        raise RuntimeError("downgrade is limited to isolated synthetic test schemas; restore production from verified backup")
    for table in reversed(CREATED_TABLES):
        op.drop_table(table)