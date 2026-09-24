"""Migration chain contract for 0011_notifications (T153)."""

from __future__ import annotations

import importlib


def migration_module():
    return importlib.import_module("migrations.versions.0011_notifications")


def test_notification_migration_creates_only_notifications():
    migration = migration_module()
    assert migration.revision == "0011_notifications"
    assert migration.down_revision == "0010_operations"
    assert set(migration.CREATED_TABLES) == {"notifications"}
    assert callable(migration.upgrade) and callable(migration.downgrade)
