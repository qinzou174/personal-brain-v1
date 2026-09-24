"""DeletionPlan, DeletionAction and retention mappings.

Reuses ReviewInboxItem/Conflict; adds a value-free deletion ledger. Created once.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0008_lifecycle_deletion"
down_revision = "0007_retrieval_context"
branch_labels = None
depends_on = None

SOURCE_VERSION = "0007_retrieval_context"
TARGET_VERSION = revision
AFFECTED_CANONICAL = ("DeletionPlan", "DeletionAction")
AFFECTED_DERIVED = ()
LOCK_STORAGE_IMPACT = "Adds 2 empty canonical deletion tables; no rows rewritten."
BACKUP_PREREQUISITE = "Empty synthetic database only; any populated target requires an independently verified restore point before migration."
RESTORE_STRATEGY = "Production rollback is restore from the verified pre-migration backup; downgrade is restricted to isolated brain_migration_test_* schemas."
PREFLIGHT_SQL = "SELECT to_regclass('review_inbox_items') IS NOT NULL AS core_exists"

CREATED_TABLES = ("deletion_plans", "deletion_actions")
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
        "deletion_plans", _id(), _owner(),
        sa.Column("requested_targets", JSONB, nullable=False),
        sa.Column("impact_graph", JSONB, nullable=False),
        sa.Column("policy_actions", JSONB, nullable=False),
        sa.Column("backup_implications", JSONB),
        sa.Column("risk", sa.String(32), nullable=False),
        sa.Column("confirmation_state", sa.String(16), nullable=False),
        sa.Column("confirmation_identity", sa.String(64)),
        sa.Column("confirmation_time", sa.DateTime(timezone=True)),
        sa.Column("execution_state", sa.String(16), nullable=False),
        sa.Column("reconciliation_state", sa.String(16), nullable=False),
        sa.Column("audit_ref", sa.String(128)),
        *_timestamps(),
        sa.CheckConstraint("confirmation_state IN ('pending','confirmed','rejected','expired')", name="deletion_confirmation_state_allowed"),
        sa.CheckConstraint("execution_state IN ('preview','executing','completed','failed')", name="deletion_execution_state_allowed"),
    )
    op.create_table(
        "deletion_actions", _id(), _owner(),
        sa.Column("plan_id", UUID(as_uuid=True), sa.ForeignKey("deletion_plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("produced_purged", sa.Boolean(), nullable=False),
        sa.Column("backup_purge_due", sa.Boolean(), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True)),
        sa.Column("opaque_deletion_version", sa.BigInteger(), nullable=False),
        *_timestamps(),
        # The ledger records only opaque IDs/version/time; no body is ever retained.
        sa.CheckConstraint("action IN ('delete','detach','tombstone','recompute')", name="deletion_action_allowed"),
    )
    op.create_index("ix_deletion_actions_plan", "deletion_actions", ["owner_id", "plan_id"])


def downgrade() -> None:
    schema = op.get_bind().scalar(sa.text("SELECT current_schema()"))
    if not isinstance(schema, str) or not schema.startswith("brain_migration_test_"):
        raise RuntimeError("downgrade is limited to isolated synthetic test schemas; restore production from verified backup")
    for table in reversed(CREATED_TABLES):
        op.drop_table(table)