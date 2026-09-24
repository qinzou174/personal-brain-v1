"""US5 Scenario G/H: intent routing, scope-before-search and budget (T103)."""

import pytest


def test_exact_finance_query_routes_before_semantic():
    from personal_brain_domain.retrieval.router import classify_intent, route_query

    assert classify_intent("本月总额多少") == "expense_total"
    decision = route_query(intent="expense_total", scopes={"finance"}, client_id="c",
                           grants=[{"client_id": "c", "effect": "allow", "scope_pattern": "finance"}])
    assert decision.authority == "exact"


def test_scope_before_search_denies_candidate_access():
    from personal_brain_domain.retrieval.router import route_query

    denied = []
    decision = route_query(intent="fuzzy_idea", scopes={"diary"}, client_id="project-only",
                           grants=[{"client_id": "project-only", "effect": "allow", "scope_pattern": "project"}],
                           on_denied=lambda: denied.append(True))
    assert decision is None and denied == [True]


def test_budget_enforced_and_warnings_preserved():
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_domain.retrieval.budget import compile_within_budget

    with pytest.raises(BrainError) as caught:
        compile_within_budget(items=[{"bytes": 5000}], ceiling=2000, mandatory_warnings=("stale",))
    assert caught.value.code == "PAYLOAD_TOO_LARGE"
    ok = compile_within_budget(items=[{"bytes": 1000}], ceiling=2000, mandatory_warnings=("stale",))
    assert ok["warnings"] == ["stale"]
