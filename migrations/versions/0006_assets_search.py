"""Asset + SearchIndexEntry mappings; reuse core DerivedContent.

Only Asset, AssetBlob and SearchIndexEntry are created here. ``(sha256, size)``
is unique; secret sensitivity is invalid for ordinary search entries.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.dialects.postgresql import TSVECTOR


revision = "0006_assets_search"
down_revision = "0005_project_brain"
branch_labels = None
depends_on = None

SOURCE_VERSION = "0005_project_brain"
TARGET_VERSION = revision
AFFECTED_CANONICAL = ("Asset", "AssetBlob", "SearchIndexEntry")
AFFECTED_DERIVED = ()
LOCK_STORAGE_IMPACT = "Adds 3 empty canonical asset/search tables; no rows rewritten."
BACKUP_PREREQUISITE = "Empty synthetic database only; any populated target requires an independently verified restore point before migration."
RESTORE_STRATEGY = "Production rollback is restore from the verified pre-migration backup; downgrade is restricted to isolated brain_migration_test_* schemas."
PREFLIGHT_SQL = "SELECT to_regclass('projects') IS NOT NULL AS core_exists"

CREATED_TABLES = ("asset_blobs", "assets", "search_index_entries")
POST_VALIDATION_SQL = (
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = current_schema() "
    "AND table_name IN (" + ",".join("'" + name + "'" for name in CREATED_TABLES) + ")"
)

ASSET_INTEGRITY = "'unknown','valid','missing','corrupted','hash_mismatch'"
ASSET_PROCESSING = "'stored','queued','processing','ready','partial','failed'"


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
    # Keep the shared type extension outside the application/test schema so an
    # isolated schema can be dropped cleanly after reverse migration.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public")
    op.execute("SELECT set_config('search_path', current_schema() || ',public', true)")
    op.create_table(
        "asset_blobs", _id(), _owner(),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_backend", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("reference_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_integrity_check_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.UniqueConstraint("sha256", "size_bytes", name="uq_asset_blob_identity"),
    )
    op.create_table(
        "assets", _id(), _owner(),
        sa.Column("blob_id", UUID(as_uuid=True), sa.ForeignKey("asset_blobs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_backend", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("raw_inputs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_metadata", JSONB),
        sa.Column("capture_at", sa.DateTime(timezone=True)),
        sa.Column("location_evidence", JSONB),
        sa.Column("integrity_state", sa.String(16), nullable=False),
        sa.Column("processing_state", sa.String(16), nullable=False),
        sa.Column("retention", sa.String(32), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(f"integrity_state IN ({ASSET_INTEGRITY})", name="asset_integrity_allowed"),
        sa.CheckConstraint(f"processing_state IN ({ASSET_PROCESSING})", name="asset_processing_allowed"),
        sa.CheckConstraint("length(original_name) <= 255", name="asset_name_bound"),
    )
    op.create_table(
        "search_index_entries", _id(), _owner(),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", UUID(as_uuid=True), nullable=False),
        sa.Column("authorized_scope", sa.String(256), nullable=False),
        sa.Column("sensitivity", sa.String(32), nullable=False),
        sa.Column("canonicality", sa.String(16), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("freshness", sa.String(16), nullable=False),
        sa.Column("searchable_text", sa.Text()),
        sa.Column(
            "search_document", TSVECTOR(),
            sa.Computed("to_tsvector('simple', coalesce(searchable_text, ''))", persisted=True),
        ),
        # Dimension is enforced per vector_model_version by the indexing service;
        # unbounded VECTOR permits side-by-side model migrations without mixed-distance ranking.
        sa.Column("embedding", VECTOR()),
        sa.Column("vector_model_version", sa.String(64)),
        sa.Column("metadata_filters", JSONB),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("sensitivity IN ('normal','personal','private','highly_private')", name="search_sensitivity_allowed"),
        sa.CheckConstraint("freshness IN ('fresh','stale','unknown')", name="search_freshness_allowed"),
    )
    op.create_index("ix_asset_blob_identity", "asset_blobs", ["owner_id", "sha256"])
    op.create_index("ix_search_index_scope", "search_index_entries", ["owner_id", "authorized_scope", "sensitivity"])
    op.create_index("ix_search_index_fts", "search_index_entries", ["search_document"], postgresql_using="gin")
    op.create_index("ix_search_index_vector_version", "search_index_entries", ["owner_id", "authorized_scope", "vector_model_version"])


def downgrade() -> None:
    schema = op.get_bind().scalar(sa.text("SELECT current_schema()"))
    if not isinstance(schema, str) or not schema.startswith("brain_migration_test_"):
        raise RuntimeError("downgrade is limited to isolated synthetic test schemas; restore production from verified backup")
    for table in reversed(CREATED_TABLES):
        op.drop_table(table)
