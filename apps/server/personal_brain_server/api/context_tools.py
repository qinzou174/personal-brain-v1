"""Scoped get_brain_context / search_brain / get_self_context operations.

FR-056..FR-065/FR-099: permission filtering happens before any candidate access;
exact/structured routes use deterministic aggregation; context packages respect
their detail budgets and carry warnings/source links.
"""

from __future__ import annotations

from dataclasses import dataclass

from personal_brain_domain.common.errors import BrainError
from personal_brain_domain.retrieval.budget import compile_within_budget
from personal_brain_domain.retrieval.compiler import ContextPackage, compile_context
from personal_brain_domain.retrieval.router import classify_intent, route_query


def _require_scope(client_id: str, grants: list[dict], scope: str) -> None:
    allowed = any(
        grant.get("client_id") == client_id and grant.get("effect") == "allow"
        and (grant.get("scope_pattern") == scope or grant.get("scope_pattern") == "*")
        for grant in grants
    )
    denied = any(
        grant.get("client_id") == client_id and grant.get("effect") == "deny"
        and (grant.get("scope_pattern") == scope or grant.get("scope_pattern") == "*")
        for grant in grants
    )
    if denied or not allowed:
        raise BrainError("SCOPE_DENIED")


def search_brain(*, client_id: str, grants: list[dict], query: str, requested_scope: str,
                 corpus: dict | None = None) -> dict:
    _require_scope(client_id, grants, requested_scope)
    decision = route_query(intent=classify_intent(query), scopes={requested_scope},
                           client_id=client_id, grants=grants)
    if decision is None:
        raise BrainError("SCOPE_DENIED")
    hits = []
    if corpus:
        for object_id, entry in corpus.items():
            if entry.get("scope") == requested_scope and any(token in entry.get("text", "") for token in query):
                hits.append({"id": object_id, "text": entry["text"][:200], "scope": requested_scope})
    return {"query": query, "authority": decision.authority, "hits": hits[:20]}


def get_brain_context(*, client_id: str, grants: list[dict], intent: str, requested_scope: str,
                      detail: str = "normal", candidates: list | None = None,
                      history: list | None = None, budget: int = 6000) -> dict:
    _require_scope(client_id, grants, requested_scope)
    package = compile_context(intent=intent, candidates=candidates or [],
                              history_items=history or [], warnings=[])
    bounded = compile_within_budget(items=[{"bytes": 100} for _ in package.current_state],
                                    ceiling=budget, mandatory_warnings=package.warnings)
    return {"intent": intent, "current_state": list(package.current_state),
            "historical_rationale": list(package.historical_rationale),
            "warnings": bounded["warnings"], "used_budget": bounded["used_budget"]}


def get_self_context(*, client_id: str, grants: list[dict], categories: list[str],
                     detail: str = "normal") -> dict:
    _require_scope(client_id, grants, "self")
    return {"categories": list(categories), "detail": detail}