"""Migration chain contract for 0003_lineage_constraints (T058)."""

from __future__ import annotations

import importlib


def migration_module():
    return importlib.import_module("migrations.versions.0003_lineage_constraints")


def test_lineage_migration_links_and_adds_only_indexes():
    migration = migration_module()
    assert migration.revision == "0003_lineage_constraints"
    assert migration.down_revision == "0002_life_records"
    assert migration.CREATED_TABLES == ()
    assert "derivation_edges" in migration.PREFLIGHT_SQL
    assert callable(migration.upgrade) and callable(migration.downgrade)
