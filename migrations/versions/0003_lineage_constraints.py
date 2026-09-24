"""Lineage target indexes and source-resolution constraints.

Reuses foundation DerivationEdge/DerivedContent and US1 Experience. Adds target
indexes so provenance queries can resolve a derived object to its live sources
and a source to every derivation that depends on it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0003_lineage_constraints"
down_revision = "0002_life_records"
branch_labels = None
depends_on = None

SOURCE_VERSION = "0002_life_records"
TARGET_VERSION = revision
AFFECTED_CANONICAL = ()
AFFECTED_DERIVED = ("DerivationEdge", "DerivedContent")
LOCK_STORAGE_IMPACT = "Adds two indexes on existing derivation tables; no rows rewritten."
BACKUP_PREREQUISITE = "Empty synthetic database only; any populated target requires an independently verified restore point before migration."
RESTORE_STRATEGY = "Production rollback is restore from the verified pre-migration backup; downgrade is restricted to isolated brain_migration_test_* schemas."
PREFLIGHT_SQL = "SELECT to_regclass('derivation_edges') IS NOT NULL AS core_exists"

CREATED_TABLES = ()
POST_VALIDATION_SQL = (
    "SELECT (SELECT count(*) FROM pg_indexes WHERE schemaname = current_schema() AND tablename IN ('derivation_edges','derived_contents')) "
    ">= 2 AS lineage_indexes_present"
)


def upgrade() -> None:
    op.create_index("ix_derivation_derived_target", "derivation_edges", ["owner_id", "derived_type", "derived_id"])
    op.create_index("ix_derived_content_target", "derived_contents", ["owner_id", "target_type", "target_id", "state"])


def downgrade() -> None:
    schema = op.get_bind().scalar(sa.text("SELECT current_schema()"))
    if not isinstance(schema, str) or not schema.startswith("brain_migration_test_"):
        raise RuntimeError("downgrade is limited to isolated synthetic test schemas; restore production from verified backup")
    op.drop_index("ix_derived_content_target", table_name="derived_contents")
    op.drop_index("ix_derivation_derived_target", table_name="derivation_edges")
