"""Migration chain contract for 0007_retrieval_context (T104)."""

from __future__ import annotations

import importlib


def migration_module():
    return importlib.import_module("migrations.versions.0007_retrieval_context")


def test_context_migration_creates_only_new_tables():
    migration = migration_module()
    assert migration.revision == "0007_retrieval_context"
    assert migration.down_revision == "0006_assets_search"
    assert set(migration.CREATED_TABLES) == {"context_requests", "context_packages"}
    assert callable(migration.upgrade) and callable(migration.downgrade)
