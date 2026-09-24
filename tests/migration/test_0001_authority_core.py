"""Red-first migration contract; run only against an isolated *_test PostgreSQL DB."""

from __future__ import annotations

import importlib
import os
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


CORE_TABLES = {
    "owners",
    "clients",
    "credentials",
    "oauth_grants",
    "permission_grants",
    "intake_requests",
    "raw_inputs",
    "audit_events",
    "idempotency_records",
    "jobs",
    "derivation_edges",
    "derived_contents",
    "review_inbox_items",
}


def migration_module():
    return importlib.import_module("migrations.versions.0001_authority_core")


def test_migration_declares_preflight_postvalidation_and_restore_strategy():
    migration = migration_module()
    assert migration.revision == "0001_authority_core"
    assert migration.down_revision is None
    assert migration.SOURCE_VERSION == "empty"
    assert migration.TARGET_VERSION == "0001_authority_core"
    assert migration.PREFLIGHT_SQL.strip()
    assert migration.POST_VALIDATION_SQL.strip()
    assert migration.RESTORE_STRATEGY.strip()
    assert set(migration.CREATED_TABLES) == CORE_TABLES
    assert callable(migration.upgrade) and callable(migration.downgrade)


def test_migration_round_trip_and_postvalidation_in_isolated_schema():
    dsn = os.environ.get("BRAIN_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("BRAIN_TEST_POSTGRES_DSN unavailable; authoritative PostgreSQL evidence is tracked separately")
    if not (make_url(dsn).database or "").endswith("_test"):
        pytest.fail("migration test database name must end with _test")

    migration = migration_module()
    schema = "brain_migration_test_" + uuid4().hex
    engine = create_engine(dsn)
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text("SELECT set_config('search_path', :schema, true)"), {"schema": schema})
            assert connection.scalar(text(migration.PREFLIGHT_SQL)) is True
            migration.op = Operations(MigrationContext.configure(connection))
            migration.upgrade()
            assert CORE_TABLES <= set(inspect(connection).get_table_names(schema=schema))
            assert connection.scalar(text(migration.POST_VALIDATION_SQL)) == len(CORE_TABLES)
            migration.downgrade()
            assert not (CORE_TABLES & set(inspect(connection).get_table_names(schema=schema)))
            connection.execute(text(f'DROP SCHEMA "{schema}"'))
    finally:
        engine.dispose()
