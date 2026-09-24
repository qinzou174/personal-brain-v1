"""Stable, value-free domain errors and protocol-neutral error envelopes."""

from __future__ import annotations

from typing import Any


STABLE_CODES = frozenset({
    "AUTH_REQUIRED", "AUTH_INVALID", "CLIENT_REVOKED", "TOOL_DENIED", "SCOPE_DENIED",
    "SENSITIVITY_DENIED", "VALIDATION_FAILED", "NOT_FOUND", "VERSION_CONFLICT",
    "IDEMPOTENCY_CONFLICT", "CONFIRMATION_REQUIRED", "CONFIRMATION_EXPIRED",
    "STALE_PROJECT_CONTEXT", "SECRET_REJECTED", "PAYLOAD_TOO_LARGE", "ARCHIVE_LIMIT_EXCEEDED",
    "WORKSPACE_BOUNDARY_VIOLATION", "BRAIN_UNAVAILABLE", "JOB_ACCEPTED",
    "DEPENDENCY_CONFLICT", "INTERNAL_SAFE_ERROR",
    # Protocol-level rejections kept distinct from credential failures: a denied
    # Origin or a lost MCP session must not push clients into rotating (and thus
    # breaking) a perfectly valid credential.
    "ORIGIN_NOT_ALLOWED", "MCP_SESSION_REQUIRED",
})

_CONFLICT_CODES = frozenset({"VERSION_CONFLICT", "IDEMPOTENCY_CONFLICT", "DEPENDENCY_CONFLICT"})
_UNAVAILABLE_CODES = frozenset({"BRAIN_UNAVAILABLE"})
_FAILED_CODES = frozenset({"INTERNAL_SAFE_ERROR"})
_RETRYABLE_CODES = frozenset({"BRAIN_UNAVAILABLE", "STALE_PROJECT_CONTEXT"})

_SAFE_MESSAGES = {
    "AUTH_REQUIRED": "Authentication is required.",
    "AUTH_INVALID": "Authentication is invalid.",
    "CLIENT_REVOKED": "Client access has been revoked.",
    "TOOL_DENIED": "This operation is not permitted.",
    "SCOPE_DENIED": "The requested scope is not permitted.",
    "SENSITIVITY_DENIED": "The requested sensitivity is not permitted.",
    "VALIDATION_FAILED": "The request is invalid.",
    "NOT_FOUND": "The requested item is unavailable.",
    "VERSION_CONFLICT": "The item changed; refresh before retrying.",
    "IDEMPOTENCY_CONFLICT": "The request key was used for different content.",
    "CONFIRMATION_REQUIRED": "Owner confirmation is required.",
    "CONFIRMATION_EXPIRED": "Owner confirmation has expired.",
    "STALE_PROJECT_CONTEXT": "Current project evidence is unavailable or stale.",
    "SECRET_REJECTED": "Secret-like material cannot enter ordinary storage.",
    "PAYLOAD_TOO_LARGE": "The submitted payload exceeds a documented limit.",
    "ARCHIVE_LIMIT_EXCEEDED": "Archive analysis exceeded a documented limit.",
    "WORKSPACE_BOUNDARY_VIOLATION": "The requested path is outside the approved workspace.",
    "BRAIN_UNAVAILABLE": "The Brain is temporarily unavailable.",
    "DEPENDENCY_CONFLICT": "A dependent item prevents this change.",
    "INTERNAL_SAFE_ERROR": "The operation failed safely.",
    "ORIGIN_NOT_ALLOWED": "This request origin is not allowed.",
    "MCP_SESSION_REQUIRED": "The MCP session is missing or expired; initialize again.",
}


class BrainError(Exception):
    """A safe public code; arbitrary upstream exception text is never retained."""

    def __init__(self, code: str):
        if code not in STABLE_CODES or code == "JOB_ACCEPTED":
            raise ValueError("invalid domain error code")
        self.code = code
        super().__init__(_SAFE_MESSAGES[code])

    def __repr__(self) -> str:
        return f"BrainError(code={self.code!r})"


def safe_error(
    error: Exception,
    *,
    code: str | None = None,
    correlation_id: str | None = None,
    retry_after: int | None = None,
    audit_ref: str | None = None,
) -> dict[str, Any]:
    """Map any exception to a body-free stable envelope.

    ``error`` is intentionally not formatted, serialized, logged, or chained.
    Only the trusted caller-supplied code or a BrainError code can be exposed.
    """
    selected = error.code if isinstance(error, BrainError) else (code or "INTERNAL_SAFE_ERROR")
    if selected not in _SAFE_MESSAGES:
        selected = "INTERNAL_SAFE_ERROR"
    status = "conflict" if selected in _CONFLICT_CODES else "unavailable" if selected in _UNAVAILABLE_CODES else "failed" if selected in _FAILED_CODES else "rejected"
    envelope: dict[str, Any] = {
        "request_id": correlation_id,
        "correlation_id": correlation_id,
        "status": status,
        "code": selected,
        "message": _SAFE_MESSAGES[selected],
        "retryable": selected in _RETRYABLE_CODES,
        "details": {},
    }
    if retry_after is not None and selected in _RETRYABLE_CODES and isinstance(retry_after, int) and 0 <= retry_after <= 3600:
        envelope["retry_after"] = retry_after
    if audit_ref is not None:
        envelope["audit_ref"] = audit_ref
    return envelope
