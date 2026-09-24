"""Notification trigger, candidate, suppression, delivery and acknowledgement mappings.

Created once; external channels are optional and preauthorized.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0011_notifications"
down_revision = "0010_operations"
branch_labels = None
depends_on = None

SOURCE_VERSION = "0010_operations"
TARGET_VERSION = revision
AFFECTED_CANONICAL = ("Notification",)
AFFECTED_DERIVED = ()
LOCK_STORAGE_IMPACT = "Adds 1 empty canonical notification table; no rows rewritten."
BACKUP_PREREQUISITE = "Empty synthetic database only; any populated target requires an independently verified restore point before migration."
RESTORE_STRATEGY = "Production rollback is restore from the verified pre-migration backup; downgrade is restricted to isolated brain_migration_test_* schemas."
PREFLIGHT_SQL = "SELECT to_regclass('health_findings') IS NOT NULL AS core_exists"

CREATED_TABLES = ("notifications",)
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
        "notifications", _id(), _owner(),
        sa.Column("trigger_type", sa.String(32), nullable=False),
        sa.Column("source_object_id", UUID(as_uuid=True)),
        sa.Column("risk", sa.String(16), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False),
        sa.Column("dedupe_key", sa.String(512), nullable=False),
        sa.Column("cooldown_group", sa.String(64)),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(512)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint("trigger_type IN ('todo_deadline','sync_index_failure','backup_storage_failure','brain_health_failure','preference_trend')", name="notification_trigger_allowed"),
        sa.CheckConstraint("channel IN ('inbox','email','push','other')", name="notification_channel_allowed"),
        sa.CheckConstraint("state IN ('candidate','suppressed','queued','delivered','failed','acknowledged')", name="notification_state_allowed"),
    )
    op.create_index("ix_notifications_dedupe", "notifications", ["owner_id", "dedupe_key", "created_at"])


def downgrade() -> None:
    schema = op.get_bind().scalar(sa.text("SELECT current_schema()"))
    if not isinstance(schema, str) or not schema.startswith("brain_migration_test_"):
        raise RuntimeError("downgrade is limited to isolated synthetic test schemas; restore production from verified backup")
    op.drop_table("notifications")