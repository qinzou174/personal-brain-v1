"""Migration chain contract for 0006_assets_search (T092)."""

from __future__ import annotations

import importlib


def migration_module():
    return importlib.import_module("migrations.versions.0006_assets_search")


def test_asset_migration_creates_only_new_tables():
    migration = migration_module()
    assert migration.revision == "0006_assets_search"
    assert migration.down_revision == "0005_project_brain"
    assert set(migration.CREATED_TABLES) == {"assets", "asset_blobs", "search_index_entries"}
    assert callable(migration.upgrade) and callable(migration.downgrade)


def test_blob_identity_and_search_sensitivity_constraints_declared():
    source = open(migration_module().__file__, encoding="utf-8").read()
    assert "uq_asset_blob_identity" in source
    assert "search_sensitivity_allowed" in source
    assert "asset_processing_allowed" in source