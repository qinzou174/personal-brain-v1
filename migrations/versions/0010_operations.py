"""BackupSet, RestoreVerification, HealthFinding and integrity-history mappings.

Migration-evidence and integrity history included; created once.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0010_operations"
down_revision = "0009_external_sources"
branch_labels = None
depends_on = None

SOURCE_VERSION = "0009_external_sources"
TARGET_VERSION = revision
AFFECTED_CANONICAL = ("BackupSet", "RestoreVerification", "HealthFinding")
AFFECTED_DERIVED = ()
LOCK_STORAGE_IMPACT = "Adds 3 empty canonical operations tables; no rows rewritten."
BACKUP_PREREQUISITE = "Empty synthetic database only; any populated target requires an independently verified restore point before migration."
RESTORE_STRATEGY = "Production rollback is restore from the verified pre-migration backup; downgrade is restricted to isolated brain_migration_test_* schemas."
PREFLIGHT_SQL = "SELECT to_regclass('deletion_plans') IS NOT NULL AS core_exists"

CREATED_TABLES = ("backup_sets", "restore_verifications", "health_findings")
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
        "backup_sets", _id(), _owner(),
        sa.Column("inventory", JSONB, nullable=False),
        sa.Column("covered_revision", sa.String(64)),
        sa.Column("covered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("database_artifact", sa.String(512), nullable=False),
        sa.Column("asset_manifest", JSONB, nullable=False),
        sa.Column("configuration_manifest", JSONB),
        sa.Column("retention_tier", sa.String(16), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("integrity_result", sa.String(64)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint("retention_tier IN ('daily','weekly','monthly')", name="backup_tier_allowed"),
        sa.CheckConstraint("state IN ('pending','completed','failed','expired')", name="backup_state_allowed"),
    )
    op.create_table(
        "restore_verifications", _id(), _owner(),
        sa.Column("backup_id", UUID(as_uuid=True), sa.ForeignKey("backup_sets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("isolated_target_id", sa.String(256)),
        sa.Column("restored_record_counts", JSONB),
        sa.Column("relationship_checks", JSONB),
        sa.Column("permission_cases", JSONB),
        sa.Column("representative_queries", JSONB),
        sa.Column("asset_hashes", JSONB),
        sa.Column("result", sa.String(16), nullable=False),
        sa.Column("failures", JSONB),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("result IN ('passed','failed','pending')", name="restore_result_allowed"),
    )
    op.create_table(
        "health_findings", _id(), _owner(),
        sa.Column("component", sa.String(64), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_summary", sa.String(512)),
        sa.Column("affected_objects", JSONB),
        sa.Column("remediation_guidance", sa.String(512)),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint("severity IN ('info','warn','critical')", name="health_severity_allowed"),
        sa.CheckConstraint("status IN ('healthy','degraded','failed','unknown')", name="health_status_allowed"),
    )
    op.create_index("ix_health_findings_component", "health_findings", ["owner_id", "component", "status"])


def downgrade() -> None:
    schema = op.get_bind().scalar(sa.text("SELECT current_schema()"))
    if not isinstance(schema, str) or not schema.startswith("brain_migration_test_"):
        raise RuntimeError("downgrade is limited to isolated synthetic test schemas; restore production from verified backup")
    for table in reversed(CREATED_TABLES):
        op.drop_table(table)