"""Migration chain contract for 0010_operations (T141)."""

from __future__ import annotations

import importlib


def migration_module():
    return importlib.import_module("migrations.versions.0010_operations")


def test_operations_migration_creates_only_new_tables():
    migration = migration_module()
    assert migration.revision == "0010_operations"
    assert migration.down_revision == "0009_external_sources"
    assert set(migration.CREATED_TABLES) == {"backup_sets", "restore_verifications", "health_findings"}
    assert callable(migration.upgrade) and callable(migration.downgrade)
