"""Migration chain contract for 0004_memory_self_model (T065)."""

from __future__ import annotations

import importlib


def migration_module():
    return importlib.import_module("migrations.versions.0004_memory_self_model")


def test_memory_migration_creates_only_new_tables():
    migration = migration_module()
    assert migration.revision == "0004_memory_self_model"
    assert migration.down_revision == "0003_lineage_constraints"
    assert set(migration.CREATED_TABLES) == {"memories", "self_claims", "evidence", "conflicts"}
    assert callable(migration.upgrade) and callable(migration.downgrade)


def test_self_claim_class_c_gate_declared():
    source = open(migration_module().__file__, encoding="utf-8").read()
    assert "class_c_gate" in source
    assert "self_category_allowed" in source
    assert "conflict_two_participants" in source