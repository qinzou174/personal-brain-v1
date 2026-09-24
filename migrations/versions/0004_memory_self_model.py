"""Memory and Self Model mappings: Memory, SelfClaim, Evidence, Conflict.

Reuses foundation ReviewInboxItem and versioned proposals. Added entities are
created once; later migrations reference them.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0004_memory_self_model"
down_revision = "0003_lineage_constraints"
branch_labels = None
depends_on = None

SOURCE_VERSION = "0003_lineage_constraints"
TARGET_VERSION = revision
AFFECTED_CANONICAL = ("Memory", "SelfClaim", "Evidence", "Conflict")
AFFECTED_DERIVED = ()
LOCK_STORAGE_IMPACT = "Adds 4 empty canonical memory/self-model tables; no rows rewritten."
BACKUP_PREREQUISITE = "Empty synthetic database only; any populated target requires an independently verified restore point before migration."
RESTORE_STRATEGY = "Production rollback is restore from the verified pre-migration backup; downgrade is restricted to isolated brain_migration_test_* schemas."
PREFLIGHT_SQL = "SELECT to_regclass('review_inbox_items') IS NOT NULL AS core_exists"

CREATED_TABLES = ("memories", "self_claims", "evidence", "conflicts")
POST_VALIDATION_SQL = (
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = current_schema() "
    "AND table_name IN (" + ",".join("'" + name + "'" for name in CREATED_TABLES) + ")"
)

MEMORY_LIFECYCLE = "'candidate','active','temporary','historical','superseded','expired','archived','deleted'"
SELF_CATEGORY = "'preference','aesthetic','value','working_style','communication_style','interest','habit','goal','philosophy'"
SELF_CLASS = "'A','B','C'"
ESTABLISHMENT = "'candidate','established','explicit'"
REVIEW = "'none','pending_confirmation','rejected'"
STANCE = "'supports','contradicts','neutral'"


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


def upgrade() -> None:
    op.create_table(
        "memories", _id(), _owner(),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("lifecycle_state", sa.String(16), nullable=False),
        sa.Column("source_class", sa.String(64), nullable=False),
        sa.Column("confidence", sa.String(32)),
        sa.Column("confidence_inputs", JSONB),
        sa.Column("retention_policy", sa.String(32), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("context", sa.String(256)),
        sa.Column("exceptions", JSONB),
        sa.Column("strength", sa.String(16)),
        sa.Column("superseded_by_id", UUID(as_uuid=True)),
        _source(),
        *_timestamps(), _version(),
        sa.CheckConstraint(f"lifecycle_state IN ({MEMORY_LIFECYCLE})", name="memory_lifecycle_allowed"),
        sa.CheckConstraint("valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from", name="memory_interval_order"),
    )
    op.create_table(
        "self_claims", _id(), _owner(),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("policy_class", sa.String(1), nullable=False),
        sa.Column("lifecycle_state", sa.String(16), nullable=False),
        sa.Column("establishment", sa.String(16), nullable=False),
        sa.Column("review", sa.String(32), nullable=False),
        sa.Column("correction_events", JSONB),
        sa.Column("confidence_inputs", JSONB),
        sa.Column("evidence_summary", JSONB),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("context", sa.String(256)),
        sa.Column("exceptions", JSONB),
        sa.Column("confirmation_identity", sa.String(64)),
        sa.Column("confirmation_time", sa.DateTime(timezone=True)),
        _source(),
        *_timestamps(), _version(),
        sa.CheckConstraint(f"category IN ({SELF_CATEGORY})", name="self_category_allowed"),
        sa.CheckConstraint(f"policy_class IN ({SELF_CLASS})", name="self_policy_class_allowed"),
        sa.CheckConstraint("policy_class != 'C' OR review = 'pending_confirmation' OR lifecycle_state IN ('active','historical','superseded')", name="class_c_gate"),
        sa.CheckConstraint(f"establishment IN ({ESTABLISHMENT})", name="self_establishment_allowed"),
        sa.CheckConstraint(f"review IN ({REVIEW})", name="self_review_allowed"),
    )
    op.create_table(
        "evidence", _id(), _owner(),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), nullable=False),
        sa.Column("stance", sa.String(16), nullable=False),
        sa.Column("source_trust", sa.String(32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("context", sa.String(256)),
        sa.Column("contribution", sa.Numeric(8, 4)),
        sa.Column("lifecycle_state", sa.String(16), nullable=False),
        *_timestamps(), _version(),
        sa.CheckConstraint(f"stance IN ({STANCE})", name="evidence_stance_allowed"),
        sa.CheckConstraint("contribution IS NULL OR (contribution >= -1 AND contribution <= 1)", name="evidence_contribution_bound"),
    )
    op.create_table(
        "conflicts", _id(), _owner(),
        sa.Column("participants", JSONB, nullable=False),
        sa.Column("conflict_type", sa.String(32), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence", JSONB),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("resolution", JSONB),
        sa.Column("resolver", sa.String(64)),
        *_timestamps(), _version(),
        sa.CheckConstraint("state IN ('open','resolved_by_time','resolved_by_user','tolerated','superseded')", name="conflict_state_allowed"),
        sa.CheckConstraint("jsonb_array_length(participants) >= 2", name="conflict_two_participants"),
    )
    op.create_index("ix_memories_lifecycle", "memories", ["owner_id", "lifecycle_state"])
    op.create_index("ix_self_claims_category", "self_claims", ["owner_id", "category", "policy_class"])
    op.create_index("ix_conflicts_state", "conflicts", ["owner_id", "state"])


def downgrade() -> None:
    schema = op.get_bind().scalar(sa.text("SELECT current_schema()"))
    if not isinstance(schema, str) or not schema.startswith("brain_migration_test_"):
        raise RuntimeError("downgrade is limited to isolated synthetic test schemas; restore production from verified backup")
    for table in reversed(CREATED_TABLES):
        op.drop_table(table)