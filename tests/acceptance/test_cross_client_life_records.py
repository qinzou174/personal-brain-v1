"""US1 Scenario A end-to-end: one capture, multi-client exact read (T045, SC-001)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tests.acceptance.conftest import AcceptanceEvidence, SOURCE_JOURNEYS, source_journey


def test_journey_mapping_and_evidence_gate(source_journey):
    if source_journey.id != "J02":
        pytest.skip("this acceptance file covers journey J02 only")
    assert "AC-01" in source_journey.ac_ids and "AC-02" in source_journey.ac_ids


def test_cross_client_life_record_scenario():
    from personal_brain_server.api.life_tools import add_expense, add_todo, list_expense_records, list_todos, reset_store

    reset_store()

    mobile = {
        "client_id": "mobile",
        "grants": [
            {"client_id": "mobile", "effect": "allow", "tool_pattern": "finance.write", "scope_pattern": "finance", "sensitivity_ceiling": "private"},
            {"client_id": "mobile", "effect": "allow", "tool_pattern": "todo.write", "scope_pattern": "todo", "sensitivity_ceiling": "private"},
        ],
    }
    desktop = {
        "client_id": "desktop",
        "grants": [
            {"client_id": "desktop", "effect": "allow", "tool_pattern": "finance.read", "scope_pattern": "finance", "sensitivity_ceiling": "normal"},
            {"client_id": "desktop", "effect": "allow", "tool_pattern": "todo.read", "scope_pattern": "todo", "sensitivity_ceiling": "normal"},
        ],
    }
    owner_timezone = "Asia/Shanghai"

    first = add_expense(client_id="mobile", grants=mobile["grants"], requested_scope="finance",
                        amount="38.0000", currency="CNY", description="午饭", idempotency_key="x-1", owner_timezone=owner_timezone)
    second = add_expense(client_id="mobile", grants=mobile["grants"], requested_scope="finance",
                         amount="26.0000", currency="CNY", description="打车", idempotency_key="x-2", owner_timezone=owner_timezone)
    todo = add_todo(client_id="mobile", grants=mobile["grants"], requested_scope="todo",
                    content="明天下午取快递", idempotency_key="x-3", owner_timezone=owner_timezone)

    # desktop (read-only) sees the exact canonical records with source references.
    expenses = list_expense_records(client_id="desktop", grants=desktop["grants"], requested_scope="finance",
                                    period="2026-09", owner_timezone=owner_timezone)
    assert expenses["total"] == "64.0000"
    assert len(expenses["records"]) == 2
    todos = list_todos(client_id="desktop", grants=desktop["grants"], requested_scope="todo",
                       owner_timezone=owner_timezone)
    assert len(todos["records"]) == 1
    assert todos["records"][0]["due_window"] == ("12:00", "18:00")
    assert first.outcome_id and todo.outcome_id
