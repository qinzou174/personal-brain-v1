"""Allow the governed-deletion tombstone for class-C self claims.

The governed deletion executor tombstones its targets with
``lifecycle_state='deleted'`` (constitution V: archive, never purge). The
``class_c_gate`` CHECK on ``self_claims`` (0004) only allowed
``active/historical/superseded`` for class-C rows, so approving a deletion
plan that included a class-C claim failed with a CheckViolation and rolled
the entire plan execution back — a class-C profile claim could never be
deleted through the governance chain (observed in production cleanup,
2026-09-26). Adding ``'deleted'`` does not weaken the gate's purpose — a
class-C claim still cannot reach ``active`` without its confirmation — it
only admits the deletion terminal state.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0014_class_c_gate_deletion"
down_revision = "0013_review_notification_trigger"
branch_labels = None
depends_on = None

SOURCE_VERSION = "0013_review_notification_trigger"
TARGET_VERSION = revision
AFFECTED_CANONICAL = ("SelfClaim",)
AFFECTED_DERIVED = ()
LOCK_STORAGE_IMPACT = "Replaces one named CHECK constraint on self_claims; no rows rewritten."
BACKUP_PREREQUISITE = "Any populated target requires an independently verified restore point before migration."
RESTORE_STRATEGY = "Production rollback is restore from the verified pre-migration backup; downgrade is restricted to isolated brain_migration_test_* schemas."
PREFLIGHT_SQL = "SELECT to_regclass('self_claims') IS NOT NULL AS self_claims_exists"

CREATED_TABLES = ()
POST_VALIDATION_SQL = (
    "SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'class_c_gate' "
    "AND pg_get_constraintdef(oid) LIKE '%deleted%') AS widened_constraint_present"
)

_BASE_GATE = (
    "policy_class != 'C' OR review = 'pending_confirmation' "
    "OR lifecycle_state IN ('active','historical','superseded'"
)
_WIDENED_GATE = _BASE_GATE + ",'deleted')"
_BASE_GATE += ")"


def upgrade() -> None:
    op.drop_constraint("class_c_gate", "self_claims", type_="check")
    op.create_check_constraint("class_c_gate", "self_claims", _WIDENED_GATE)


def downgrade() -> None:
    schema = op.get_bind().scalar(sa.text("SELECT current_schema()"))
    if not isinstance(schema, str) or not schema.startswith("brain_migration_test_"):
        raise RuntimeError("downgrade is limited to isolated synthetic test schemas; restore production from verified backup")
    op.drop_constraint("class_c_gate", "self_claims", type_="check")
    op.create_check_constraint("class_c_gate", "self_claims", _BASE_GATE)
