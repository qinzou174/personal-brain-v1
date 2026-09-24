"""US1 intake + cross-client tool contracts (T044, FR-001..FR-020, SC-003/SC-008)."""

import pytest


def test_intake_accepts_mixed_statement_and_produces_typed_records():
    from personal_brain_domain.intake.service import ingest_mixed_statement

    outcome = ingest_mixed_statement(
        text="午饭 38 CNY，打车 26 CNY，明天下午取快递。",
        client_id="mobile",
        owner_timezone="Asia/Shanghai",
        idempotency_key="k-1",
    )
    assert outcome.raw_input_id
    assert outcome.expenses_count == 2
    assert outcome.todos_count == 1
    assert outcome.review_count == 0


def test_cross_client_read_requires_grant_before_returning_sources():
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_server.api.life_tools import list_expense_records

    with pytest.raises(BrainError) as caught:
        list_expense_records(
            client_id="desktop",
            grants=[{"client_id": "desktop", "effect": "allow", "tool_pattern": "finance.read", "scope_pattern": "finance", "sensitivity_ceiling": "normal"}],
            requested_scope="diary",
        )
    assert caught.value.code in {"SCOPE_DENIED", "TOOL_DENIED"}


def test_duplicate_capture_returns_original_outcome_once():
    from personal_brain_server.api.life_tools import reset_store, save_note

    reset_store()
    grants = [{"client_id": "mobile", "effect": "allow", "tool_pattern": "knowledge.write", "scope_pattern": "knowledge", "sensitivity_ceiling": "private"}]
    first = save_note(
        client_id="mobile",
        content="午饭 38 CNY",
        idempotency_key="dup-1",
        requested_scope="knowledge",
        owner_timezone="Asia/Shanghai",
        grants=grants,
    )
    replay = save_note(
        client_id="mobile",
        content="午饭 38 CNY",
        idempotency_key="dup-1",
        requested_scope="knowledge",
        owner_timezone="Asia/Shanghai",
        grants=grants,
    )
    assert replay.status == "replay"
    assert replay.result["record_id"] == first.result["record_id"]
