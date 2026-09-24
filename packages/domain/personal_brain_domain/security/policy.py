"""Fail-closed access decision before any protected repository call."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Mapping, Sequence

from personal_brain_domain.common.errors import BrainError


_SENSITIVITY_RANK = {"normal": 0, "personal": 1, "private": 2, "highly_private": 3}
_CONFIRMATION_RISKS = frozenset({
    "high_risk_deletion", "new_recipient_external_communication", "class_c_mutation",
    "broad_permission_change", "destructive_maintenance",
})


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value.astimezone(timezone.utc)


def validate_confirmation_expiry(created_at: datetime, expires_at: datetime) -> bool:
    duration = _utc(expires_at) - _utc(created_at)
    return timedelta(0) < duration <= timedelta(minutes=15)


def evaluate_permission_epoch(*, authenticated_epoch: int, current_epoch: int) -> bool:
    """Permission changes affect new access immediately; stale epochs fail closed."""
    return authenticated_epoch == current_epoch


def _active(grant: Mapping[str, object], now: datetime) -> bool:
    start = grant.get("effective_from")
    end = grant.get("effective_to")
    return (start is None or now >= _utc(start)) and (end is None or now < _utc(end))


def _matching(
    grants: Sequence[Mapping[str, object]], client_id: object, tool: str, scope: str, now: datetime
) -> list[Mapping[str, object]]:
    # No wildcard is silently inferred. Broad grants require an explicit '*'.
    return [
        grant for grant in grants
        if grant.get("client_id") == client_id
        and _active(grant, now)
        and grant.get("tool_pattern") in (tool, "*")
        and grant.get("scope_pattern") in (scope, "*")
    ]


def authorize(
    client: Mapping[str, object],
    grants: Sequence[Mapping[str, object]],
    tool: str,
    scope: str,
    sensitivity: str,
    *,
    now: datetime,
    parent_project_scope: str | None = None,
    risk: str = "ordinary",
) -> bool:
    """Require client intersection and an active grant; explicit denies win.

    High-risk actions are *never* approved by this read-only decision. Their
    version-bound owner confirmation must be consumed transactionally by the
    later review/operation path; an untrusted boolean is not sufficient proof.
    """
    moment = _utc(now)
    if not isinstance(client.get("client_id"), str) or not client.get("client_id"):
        raise BrainError("AUTH_INVALID")
    if client.get("status") == "revoked":
        raise BrainError("CLIENT_REVOKED")
    if client.get("status") != "active" or client.get("permission_epoch") != client.get("authenticated_epoch"):
        raise BrainError("AUTH_INVALID")
    if tool not in client.get("allowed_tools", ()):
        raise BrainError("TOOL_DENIED")
    if scope not in client.get("allowed_scopes", ()):
        raise BrainError("SCOPE_DENIED")
    if sensitivity not in _SENSITIVITY_RANK:
        raise BrainError("SENSITIVITY_DENIED")
    matches = _matching(grants, client.get("client_id"), tool, scope, moment)
    if any(grant.get("effect") == "deny" for grant in matches):
        raise BrainError("TOOL_DENIED")
    allows = [grant for grant in matches if grant.get("effect") == "allow"]
    if not allows:
        raise BrainError("SCOPE_DENIED")
    if scope.startswith("module:"):
        if not parent_project_scope or not parent_project_scope.startswith("project:"):
            raise BrainError("SCOPE_DENIED")
        if parent_project_scope not in client.get("allowed_scopes", ()):
            raise BrainError("SCOPE_DENIED")
        parent_matches = _matching(grants, client.get("client_id"), tool, parent_project_scope, moment)
        if any(grant.get("effect") == "deny" for grant in parent_matches):
            raise BrainError("SCOPE_DENIED")
        if not any(grant.get("effect") == "allow" for grant in parent_matches):
            raise BrainError("SCOPE_DENIED")
        allows += [grant for grant in parent_matches if grant.get("effect") == "allow"]
    try:
        ceiling = min(_SENSITIVITY_RANK[str(grant["sensitivity_ceiling"])] for grant in allows)
    except (KeyError, ValueError):
        raise BrainError("SENSITIVITY_DENIED") from None
    if _SENSITIVITY_RANK[sensitivity] > ceiling:
        raise BrainError("SENSITIVITY_DENIED")
    if risk in _CONFIRMATION_RISKS:
        raise BrainError("CONFIRMATION_REQUIRED")
    if risk != "ordinary":
        raise BrainError("VALIDATION_FAILED")
    return True
