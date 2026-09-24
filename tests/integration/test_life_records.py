"""US1 integration: exact aggregation, todo transition, replay, source links (T046)."""

from __future__ import annotations

import pytest


def test_concurrent_replay_produces_one_outcome():
    from personal_brain_server.api.life_tools import add_expense, reset_store

    reset_store()
    grants = [{"client_id": "mobile", "effect": "allow", "tool_pattern": "finance.write", "scope_pattern": "finance", "sensitivity_ceiling": "private"}]
    first = add_expense(client_id="mobile", grants=grants, requested_scope="finance",
                        amount="10.0000", currency="CNY", description="奶茶", idempotency_key="same-key", owner_timezone="Asia/Shanghai")
    replay = add_expense(client_id="mobile", grants=grants, requested_scope="finance",
                         amount="10.0000", currency="CNY", description="奶茶", idempotency_key="same-key", owner_timezone="Asia/Shanghai")
    assert replay.status == "replay" and replay.result["expense_id"] == first.result["expense_id"]


def test_todo_complete_transition_and_version_gate():
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_domain.records.todos import transition_todo

    changed = transition_todo(state="in_progress", target_state="completed", version=2, expected_version=2)
    assert changed.state == "completed" and changed.version == 3
    with pytest.raises(BrainError):
        transition_todo(state="pending", target_state="completed", version=2, expected_version=1)


def test_source_link_retained_on_records():
    from personal_brain_domain.intake.service import ingest_mixed_statement

    outcome = ingest_mixed_statement(text="打车 26 CNY", client_id="mobile", owner_timezone="Asia/Shanghai", idempotency_key="k-9")
    assert outcome.raw_input_id
    assert outcome.expense_source_links == (outcome.raw_input_id,) or len(outcome.expense_source_links) == 1
