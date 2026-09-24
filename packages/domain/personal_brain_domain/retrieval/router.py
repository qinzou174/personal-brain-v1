"""Intent classification and deterministic structured dispatch.

FR-020/FR-056: exact structured questions route to deterministic lookup before
any probabilistic retrieval; permission/scope denial happens before any search
or index access. ER-04: money intent requires an explicit money cue — bare
substrings like "花了" (spent time/mind) or "total" (total time/people) must
not route into the exact finance path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_EXACT_INTENTS = frozenset({
    "expense_total", "todo_list", "project_task", "module_freshness", "recent_changes", "self_claim",
})


@dataclass(frozen=True)
class RouteDecision:
    authority: str  # exact | full_text | semantic | timeline | project
    denied: bool = False


_EXPENSE_PATTERNS = (
    re.compile(r"总额|总支出|总开销|总花费|费用汇总|开销"),
    re.compile(r"多少钱|多少元"),
    re.compile(r"花.{0,4}(钱|元|块|¥)"),
    re.compile(r"expense|money"),
    re.compile(r"total\s+(amount|expense|cost|money|spend\w*)"),
)
_TODO_PATTERNS = (
    re.compile(r"待办|任务清单|todo"),
)


def classify_intent(text: str) -> str:
    lowered = text.lower()
    if any(pattern.search(lowered) for pattern in _EXPENSE_PATTERNS):
        return "expense_total"
    if any(pattern.search(lowered) for pattern in _TODO_PATTERNS):
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