"""Migration chain contract for 0002_life_records (T047)."""

from __future__ import annotations

import importlib

LIFE_TABLES = {"documents", "expenses", "todos", "events", "experiences", "entities", "relations"}


def migration_module():
    return importlib.import_module("migrations.versions.0002_life_records")


def test_life_records_migration_links_to_core_and_creates_only_new_tables():
    migration = migration_module()
    assert migration.revision == "0002_life_records"
    assert migration.down_revision == "0001_authority_core"
    assert migration.PREFLIGHT_SQL.strip()
    assert set(migration.CREATED_TABLES) == LIFE_TABLES
    # Life records must never recreate foundation tables.
    assert not (LIFE_TABLES & {"raw_inputs", "intake_requests", "idempotency_records", "jobs", "audit_events"})
    assert callable(migration.upgrade) and callable(migration.downgrade)


def test_money_currency_todo_event_and_relation_constraints_declared():
    source = open(migration_module().__file__, encoding="utf-8").read()
    assert "sa.Numeric(20, 4)" in source
    assert "amount > 0" in source
    assert "expense_currency_iso" in source
    assert "todo_state_allowed" in source
    assert "event_time_order" in source
    assert "relation_canonical_only" in source
