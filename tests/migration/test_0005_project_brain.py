"""Migration chain contract for 0005_project_brain (T074)."""

from __future__ import annotations

import importlib


def migration_module():
    return importlib.import_module("migrations.versions.0005_project_brain")


def test_project_migration_creates_only_new_tables():
    migration = migration_module()
    assert migration.revision == "0005_project_brain"
    assert migration.down_revision == "0004_memory_self_model"
    assert set(migration.CREATED_TABLES) == {
        "projects", "module_cards", "project_tasks", "checkpoints", "decisions",
        "constraints", "change_events", "milestones", "workspace_observations",
    }
    assert callable(migration.upgrade) and callable(migration.downgrade)


def test_freshness_and_task_state_enums_declared():
    source = open(migration_module().__file__, encoding="utf-8").read()
    assert "module_freshness_allowed" in source
    assert "project_task_state_allowed" in source
    assert "uq_change_events_dedupe" in source or "dedupe" in source