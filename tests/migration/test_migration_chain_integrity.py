"""Full migration chain integrity: 0001..0011 linked, acyclic, no gaps (T012/T020).

Runs without PostgreSQL: it validates the chain metadata statically. The
physical round-trip requires BRAIN_TEST_POSTGRES_DSN (environment gate).
"""

from __future__ import annotations

import importlib
from pathlib import Path

VERSIONS_DIR = Path(__file__).resolve().parents[2] / "migrations" / "versions"

EXPECTED_ORDER = [
    "0001_authority_core",
    "0002_life_records",
    "0003_lineage_constraints",
    "0004_memory_self_model",
    "0005_project_brain",
    "0006_assets_search",
    "0007_retrieval_context",
    "0008_lifecycle_deletion",
    "0009_external_sources",
    "0010_operations",
    "0011_notifications",
    "0012_search_read_grants",
]


def _load(revision: str):
    return importlib.import_module(f"migrations.versions.{revision}")


def test_chain_is_contiguous_and_acyclic():
    previous = None
    seen = set()
    for revision in EXPECTED_ORDER:
        migration = _load(revision)
        assert migration.revision == revision, f"{revision}: module revision mismatch"
        assert migration.down_revision == previous, f"{revision}: breaks chain (expected {previous!r})"
        assert revision not in seen
        seen.add(revision)
        previous = revision


def test_no_orphan_or_duplicate_nodes():
    parents = [migration.down_revision for migration in (_load(r) for r in EXPECTED_ORDER) if migration.down_revision is not None]
    # Every node except the head (0012) is referenced exactly once as a parent;
    # the root (0001) has no parent. No duplicates, no gaps.
    assert len(parents) == len(EXPECTED_ORDER) - 1
    assert len(set(parents)) == len(parents)
    assert set(parents) == set(EXPECTED_ORDER) - {"0012_search_read_grants"}


def test_source_and_target_versions_line_up():
    for revision in EXPECTED_ORDER:
        migration = _load(revision)
        assert migration.SOURCE_VERSION == migration.down_revision or migration.SOURCE_VERSION == "empty"
        assert migration.TARGET_VERSION == revision
        assert migration.RESTORE_STRATEGY.strip()
        assert migration.PREFLIGHT_SQL.strip()
