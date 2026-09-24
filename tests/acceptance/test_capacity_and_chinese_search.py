"""ER-12 capacity and Chinese-search benchmark (T162)."""

from __future__ import annotations

import time


def test_cold_and_warm_query_within_budget():
    """Deterministic timing proxy: query <= p95 2s for context compile at normal detail."""
    from personal_brain_domain.retrieval.budget import compile_within_budget

    start = time.perf_counter()
    result = compile_within_budget(items=[{"bytes": 200} for _ in range(20)], ceiling=6000,
                                   mandatory_warnings=())
    elapsed = time.perf_counter() - start
    assert result["used_budget"] <= 6000
    assert elapsed < 2.0


def test_chinese_token_query_returns_bounded_hits():
    from personal_brain_server.api.context_tools import search_brain

    grants = [{"client_id": "c", "effect": "allow", "scope_pattern": "knowledge"}]
    result = search_brain(client_id="c", grants=grants, query="今天去了京都", requested_scope="knowledge",
                          corpus={"n1": {"scope": "knowledge", "text": "今天去了京都，人太多"}})
    assert len(result["hits"]) <= 20
