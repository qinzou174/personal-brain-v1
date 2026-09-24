"""Project Brain mappings: Project, ModuleCard, ProjectTask, Checkpoint, Decision,
Constraint, ChangeEvent, Milestone and WorkspaceObservation.

Includes exact Task/Module freshness enums from data-model.md; created once.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0005_project_brain"
down_revision = "0004_memory_self_model"
branch_labels = None
depends_on = None

SOURCE_VERSION = "0004_memory_self_model"
TARGET_VERSION = revision
AFFECTED_CANONICAL = (
    "Project", "ModuleCard", "ProjectTask", "Checkpoint", "Decision",
    "Constraint", "ChangeEvent", "Milestone", "WorkspaceObservation",
)
AFFECTED_DERIVED = ()
LOCK_STORAGE_IMPACT = "Adds 9 empty canonical project tables; no rows rewritten."
BACKUP_PREREQUISITE = "Empty synthetic database only; any populated target requires an independently verified restore point before migration."
RESTORE_STRATEGY = "Production rollback is restore from the verified pre-migration backup; downgrade is restricted to isolated brain_migration_test_* schemas."
PREFLIGHT_SQL = "SELECT to_regclass('events') IS NOT NULL AS core_exists"

CREATED_TABLES = (
    "projects", "module_cards", "project_tasks", "checkpoints", "decisions",
    "constraints", "change_events", "milestones", "workspace_observations",
)
POST_VALIDATION_SQL = (
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = current_schema() "
    "AND table_name IN (" + ",".join("'" + name + "'" for name in CREATED_TABLES) + ")"
)

MODULE_FRESHNESS = "'fresh','stale','unknown'"
TASK_STATE = "'planned','active','paused','completed','failed','cancelled'"


def _id():
    return sa.Column("id", UUID(as_uuid=True), primary_key=True)


def _owner():
    return sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("owners.id", ondelete="RESTRICT"), nullable=False)


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def _version():
    return sa.Column("version", sa.Integer(), nullable=False, server_default="1")


def upgrade() -> None:
    op.create_table(
        "projects", _id(), _owner(),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("goals", JSONB, nullable=False),
        sa.Column("principles", JSONB, nullable=False),
        sa.Column("technology_summary", sa.Text()),
        sa.Column("architecture_summary", sa.Text()),
        sa.Column("deployment_summary", sa.Text()),
        sa.Column("global_constraints", JSONB),
        sa.Column("directory_overview", sa.Text()),
        sa.Column("workspace_identity", sa.String(256)),
        sa.Column("repository_identity", sa.String(256)),
        sa.Column("current_revision_evidence", JSONB),
        sa.Column("lifecycle_state", sa.String(16), nullable=False),
        *_timestamps(), _version(),
    )
    op.create_table(
        "module_cards", _id(), _owner(),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("paths", JSONB, nullable=False),
        sa.Column("responsibility", sa.Text(), nullable=True),
        sa.Column("core_files", JSONB),
        sa.Column("interfaces", JSONB),
        sa.Column("dependencies", JSONB),
        sa.Column("consumers", JSONB),
        sa.Column("constraints", JSONB),
        sa.Column("indexed_revision", sa.String(64)),
        sa.Column("relevant_file_hashes", JSONB),
        sa.Column("freshness", sa.String(16), nullable=False),
        sa.Column("stale_reasons", JSONB),
        sa.Column("refreshed_at", sa.DateTime(timezone=True)),
        *_timestamps(), _version(),
        sa.CheckConstraint(f"freshness IN ({MODULE_FRESHNESS})", name="module_freshness_allowed"),
    )
    op.create_table(
        "project_tasks", _id(), _owner(),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("start_revision", sa.String(64)),
        sa.Column("end_revision", sa.String(64)),
        sa.Column("start_dirty_state", sa.Boolean()),
        sa.Column("end_dirty_state", sa.Boolean()),
        sa.Column("plan", sa.Text()),
        sa.Column("constraints", JSONB),
        sa.Column("affected_modules", JSONB),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("remaining_work", sa.Text()),
        sa.Column("final_report", sa.Text()),
        *_timestamps(), _version(),
        sa.CheckConstraint(f"state IN ({TASK_STATE})", name="project_task_state_allowed"),
    )
    op.create_table(
        "checkpoints", _id(), _owner(),
        sa.Column("task_id", UUID(as_uuid=True), sa.ForeignKey("project_tasks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("revision", sa.String(64)),
        sa.Column("dirty_files", JSONB),
        sa.Column("changed_files", JSONB),
        sa.Column("completed_work", sa.Text(), nullable=False),
        sa.Column("problems", sa.Text()),
        sa.Column("decisions", JSONB),
        sa.Column("next_step", sa.Text()),
        sa.Column("verification_evidence", sa.Text()),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(), _version(),
    )
    dedupe_fields = (
        ("decision_id", "decisions"),
        ("constraint_id", "constraints"),
        ("change_event_id", "change_events"),
        ("milestone_id", "milestones"),
    )
    for column_name, table_name in dedupe_fields:
        op.create_table(
            table_name, _id(), _owner(),
            sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("module_id", UUID(as_uuid=True)),
            sa.Column("task_id", UUID(as_uuid=True)),
            sa.Column("statement", sa.Text(), nullable=False),
            sa.Column("rationale", sa.Text()),
            sa.Column("evidence", JSONB),
            sa.Column("source_id", UUID(as_uuid=True)),
            sa.Column("valid_from", sa.DateTime(timezone=True)),
            sa.Column("valid_to", sa.DateTime(timezone=True)),
            sa.Column("lifecycle_state", sa.String(16), nullable=False),
            sa.Column("deduplication_key", sa.String(512), nullable=False),
            sa.Column("affected_modules", JSONB),
            sa.Column("revisions", JSONB),
            *_timestamps(), _version(),
            sa.UniqueConstraint("owner_id", "deduplication_key", name=f"uq_{table_name}_dedupe"),
        )
    op.create_table(
        "workspace_observations", _id(), _owner(),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("approved_root_identity", sa.String(256), nullable=False),
        sa.Column("revision", sa.String(64)),
        sa.Column("branch_ref", sa.String(256)),
        sa.Column("dirty_state", sa.Boolean()),
        sa.Column("changed_paths", JSONB),
        sa.Column("diff_summary", sa.Text()),
        sa.Column("file_hashes", JSONB),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bridge_client_id", sa.String(128)),
        *_timestamps(), _version(),
    )
    op.create_index("ix_module_cards_project", "module_cards", ["owner_id", "project_id"])
    op.create_index("ix_project_tasks_project", "project_tasks", ["owner_id", "project_id", "state"])
    op.create_index("ix_checkpoints_task", "checkpoints", ["owner_id", "task_id", "captured_at"])


def downgrade() -> None:
    schema = op.get_bind().scalar(sa.text("SELECT current_schema()"))
    if not isinstance(schema, str) or not schema.startswith("brain_migration_test_"):
        raise RuntimeError("downgrade is limited to isolated synthetic test schemas; restore production from verified backup")
    for table in reversed(CREATED_TABLES):
        op.drop_table(table)