"""Chunk-level semantic index for long documents (search_index_chunks).

A long document indexed with a single whole-document embedding is semantically
diluted: the vector averages every topic, so a query about one specific section
finds the card weak (observed 2026-09-26: a 15.4KB handoff doc was lexical
rank 1 yet absent from the semantic top-50, and RRF's single-list presence gave
it a fused score no dual-list card could lose to). The fix indexes long cards
as focused chunks: the chunk table carries one embedding per ~600-character
slice, the semantic list takes each parent's best chunk, and the lexical list
plus RRF stay untouched.

The chunk table stores *only* the semantic index: authorization
(scope/sensitivity), content_time and lifecycle all live on the parent
``search_index_entries`` row and are joined at query time, so there is exactly
one source of truth and nothing to drift. ``ON DELETE CASCADE`` makes chunk
lifetime strictly subordinate to the parent card: re-indexing a target deletes
and recreates its card (new entry_id), so stale chunks vanish with the old row,
including the tombstone's card-DELETE (last-writer convergence, 003).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects.postgresql import UUID


revision = "0015_search_index_chunks"
down_revision = "0014_class_c_gate_deletion"
branch_labels = None
depends_on = None

SOURCE_VERSION = "0014_class_c_gate_deletion"
TARGET_VERSION = revision
AFFECTED_CANONICAL = ("SearchIndexChunk",)
AFFECTED_DERIVED = ()
LOCK_STORAGE_IMPACT = "Adds one empty semantic-chunk index table; no rows rewritten."
BACKUP_PREREQUISITE = "Empty synthetic database only; any populated target requires an independently verified restore point before migration."
RESTORE_STRATEGY = "Production rollback is restore from the verified pre-migration backup; downgrade is restricted to isolated brain_migration_test_* schemas."
PREFLIGHT_SQL = "SELECT to_regclass('search_index_entries') IS NOT NULL AS search_entries_exist"

CREATED_TABLES = ("search_index_chunks",)
POST_VALIDATION_SQL = (
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = current_schema() "
    "AND table_name IN ('search_index_chunks')"
)


def upgrade() -> None:
    # The vector extension lives in the shared public schema (0006); keep the
    # application schema + public on the search path so the VECTOR type resolves.
    op.execute("SELECT set_config('search_path', current_schema() || ',public', true)")
    op.create_table(
        "search_index_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("owners.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("entry_id", UUID(as_uuid=True), sa.ForeignKey("search_index_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_seq", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        # Unbounded VECTOR, same per-model-version strategy as the parent card
        # (side-by-side model migrations without mixed-distance ranking).
        sa.Column("embedding", VECTOR(), nullable=False),
        sa.Column("vector_model_version", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("entry_id", "chunk_seq", name="uq_search_chunk_order"),
    )
    op.create_index("ix_search_chunk_owner", "search_index_chunks", ["owner_id", "vector_model_version"])


def downgrade() -> None:
    schema = op.get_bind().scalar(sa.text("SELECT current_schema()"))
    if not isinstance(schema, str) or not schema.startswith("brain_migration_test_"):
        raise RuntimeError("downgrade is limited to isolated synthetic test schemas; restore production from verified backup")
    op.drop_table("search_index_chunks")
