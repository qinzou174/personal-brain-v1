"""Migration chain contract for 0009_external_sources (T131)."""

from __future__ import annotations

import importlib


def migration_module():
    return importlib.import_module("migrations.versions.0009_external_sources")


def test_external_source_migration_creates_only_new_tables():
    migration = migration_module()
    assert migration.revision == "0009_external_sources"
    assert migration.down_revision == "0008_lifecycle_deletion"
    assert set(migration.CREATED_TABLES) == {"external_sources", "import_checkpoints"}
    assert callable(migration.upgrade) and callable(migration.downgrade)
