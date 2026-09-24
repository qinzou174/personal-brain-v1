"""Migration chain contract for 0008_lifecycle_deletion (T115)."""

from __future__ import annotations

import importlib


def migration_module():
    return importlib.import_module("migrations.versions.0008_lifecycle_deletion")


def test_deletion_migration_creates_only_new_tables():
    migration = migration_module()
    assert migration.revision == "0008_lifecycle_deletion"
    assert migration.down_revision == "0007_retrieval_context"
    assert set(migration.CREATED_TABLES) == {"deletion_plans", "deletion_actions"}
    assert callable(migration.upgrade) and callable(migration.downgrade)
