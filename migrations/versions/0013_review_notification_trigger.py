"""Allow the review-item notification trigger on the notifications table.

The governance closures work made ``notify_review`` write a real notification
row (channel=inbox) instead of returning a JSON string. That row carries
``trigger_type='review_item_pending'``, which the 0011 CHECK constraint does
not allow, so every review notification would dead-letter with an
IntegrityError. This revision widens the existing named CHECK in place; no
rows are rewritten and no table is created.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0013_review_notification_trigger"
down_revision = "0012_search_read_grants"
branch_labels = None
depends_on = None

SOURCE_VERSION = "0012_search_read_grants"
TARGET_VERSION = revision
AFFECTED_CANONICAL = ("Notification",)
AFFECTED_DERIVED = ()
LOCK_STORAGE_IMPACT = "Replaces one named CHECK constraint on notifications; no rows rewritten."
BACKUP_PREREQUISITE = "Any populated target requires an independently verified restore point before migration."
RESTORE_STRATEGY = "Production rollback is restore from the verified pre-migration backup; downgrade is restricted to isolated brain_migration_test_* schemas."
PREFLIGHT_SQL = "SELECT to_regclass('notifications') IS NOT NULL AS notifications_exists"

CREATED_TABLES = ()
POST_VALIDATION_SQL = (
    "SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'notification_trigger_allowed' "
    "AND pg_get_constraintdef(oid) LIKE '%review_item_pending%') AS widened_constraint_present"
)

_BASE_ENUM = "trigger_type IN ('todo_deadline','sync_index_failure','backup_storage_failure','brain_health_failure','preference_trend'"
_WIDENED_ENUM = _BASE_ENUM + ",'review_item_pending')"
_BASE_ENUM += ")"


def upgrade() -> None:
    op.drop_constraint("notification_trigger_allowed", "notifications", type_="check")
    op.create_check_constraint(
        "notification_trigger_allowed", "notifications", _WIDENED_ENUM,
    )


def downgrade() -> None:
    schema = op.get_bind().scalar(sa.text("SELECT current_schema()"))
    if not isinstance(schema, str) or not schema.startswith("brain_migration_test_"):
        raise RuntimeError("downgrade is limited to isolated synthetic test schemas; restore production from verified backup")
    op.drop_constraint("notification_trigger_allowed", "notifications", type_="check")
    op.create_check_constraint(
        "notification_trigger_allowed", "notifications", _BASE_ENUM,
    )
