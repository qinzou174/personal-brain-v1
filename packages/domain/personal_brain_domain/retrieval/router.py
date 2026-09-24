"""Intent classification and deterministic structured dispatch.

FR-020/FR-056: exact structured questions route to deterministic lookup before
any probabilistic retrieval; permission/scope denial happens before any search
or index access.
"""

from __future__ import annotations

from dataclasses import dataclass

_EXACT_INTENTS = frozenset({
    "expense_total", "todo_list", "project_task", "module_freshness", "recent_changes", "self_claim",
})


@dataclass(frozen=True)
class RouteDecision:
    authority: str  # exact | full_text | semantic | timeline | project
    denied: bool = False


def classify_intent(text: str) -> str:
    lowered = text.lower()
    if any(keyword in lowered for keyword in ("总额", "花了", "多少钱", "expense", "total")):
        return "expense_total"
    if any(keyword in lowered for keyword in ("待办", "todo", "任务清单")):
        return "todo_list"
    return "fuzzy_idea"


def route_query(*, intent: str, scopes: set[str], client_id: str, grants: list[dict], on_denied=None):
    """Route deterministically; deny before any candidate access when unauthorized."""
    allowed = any(
        grant.get("client_id") == client_id and grant.get("effect") == "allow"
        and (grant.get("scope_pattern") in scopes or grant.get("scope_pattern") == "*")
        for grant in grants
    )
    denied = any(
        grant.get("client_id") == client_id and grant.get("effect") == "deny"
        and (grant.get("scope_pattern") in scopes or grant.get("scope_pattern") == "*")
        for grant in grants
    )
    if denied or not allowed:
        if on_denied is not None:
            on_denied()
        return None
    if intent in _EXACT_INTENTS:
        return RouteDecision(authority="exact")
    return RouteDecision(authority="semantic")