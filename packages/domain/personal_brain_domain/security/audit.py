"""Body-free structured audit recording.

FR-070/FR-073/FR-076: the audit row records what happened, not the private
content it operated on. Only whitelisted metadata fields may be serialized;
request bodies, credentials, source bodies and secret fields are rejected even
if a caller passes them, so a logging mistake cannot leak private content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


_FORBIDDEN_FIELDS = frozenset({"request_body", "body", "content", "credential", "token", "secret", "source_body"})


@dataclass(frozen=True)
class AuditEvent:
    client_id: str
    correlation_id: str
    action: str
    outcome: str
    duration_ms: int
    occurred_at: datetime
    risk: str = "normal"
    tool: str | None = None
    effective_scope: str | None = None
    target_category: str | None = None
    target_id: str | None = None
    error_code: str | None = None
    authorization_decision: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)


def build_audit_event(
    *,
    client_id: str,
    action: str,
    outcome: str,
    duration_ms: int,
    correlation_id: str,
    risk: str = "normal",
    tool: str | None = None,
    effective_scope: str | None = None,
    target_category: str | None = None,
    target_id: str | None = None,
    error_code: str | None = None,
    authorization_decision: str | None = None,
    details: Mapping[str, Any] | None = None,
    **unsupported: Any,
) -> AuditEvent:
    """Build a structured audit event from whitelisted metadata only.

    Any unsupported keyword (``request_body``, ``credential``, …) is explicitly
    consumed and dropped, never serialized, and never retained.
    """
    _ = unsupported  # forbidden fields are dropped, not stored
    if duration_ms < 0:
        raise ValueError("audit duration cannot be negative")
    return AuditEvent(
        client_id=client_id,
        correlation_id=correlation_id,
        action=action,
        outcome=outcome,
        duration_ms=duration_ms,
        occurred_at=datetime.now(timezone.utc),
        risk=risk,
        tool=tool,
        effective_scope=effective_scope,
        target_category=target_category,
        target_id=target_id,
        error_code=error_code,
        authorization_decision=authorization_decision,
        details=details or {},
    )


def audit_repr(event: AuditEvent) -> str:
    """Value-free textual representation used for logging.

    ``details`` may be included only when it carries no forbidden keys; otherwise
    only the fixed metadata fields are emitted.
    """
    safe_details = {k: v for k, v in event.details.items() if k not in _FORBIDDEN_FIELDS}
    return repr(AuditEvent(
        client_id=event.client_id,
        correlation_id=event.correlation_id,
        action=event.action,
        outcome=event.outcome,
        duration_ms=event.duration_ms,
        occurred_at=event.occurred_at,
        risk=event.risk,
        tool=event.tool,
        effective_scope=event.effective_scope,
        target_category=event.target_category,
        target_id=event.target_id,
        error_code=event.error_code,
        authorization_decision=event.authorization_decision,
        details=safe_details,
    ))
