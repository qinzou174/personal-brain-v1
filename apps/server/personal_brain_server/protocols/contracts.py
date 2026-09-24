"""Protocol-neutral request/success/error envelopes and status lookup.

FR-087/088/098: adapters map MCP/HTTP/stdin requests onto these envelopes without
changing domain semantics. ``accepted`` means durable canonical or job acceptance,
never derived completion; credentials inside a payload are rejected.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping

from personal_brain_domain.common.errors import BrainError, safe_error

_CREDENTIAL_FIELDS = frozenset({"credential", "token", "password", "api_key", "authorization", "secret"})
_ACCEPTED_STATUSES = frozenset({"completed", "accepted", "pending_confirmation", "pending_sync"})


def new_request_id() -> str:
    return str(uuid.uuid4())


def build_request_envelope(
    *,
    request_id: str,
    client_id: str,
    operation: str,
    idempotency_key: str | None,
    requested_scope: str,
    payload: Mapping[str, Any],
    detail_level: str | None = None,
    expected_version: str | int | None = None,
) -> dict[str, Any]:
    """Validate a request envelope; credentials may never ride inside a payload."""
    for key in _CREDENTIAL_FIELDS:
        if key in payload:
            raise BrainError("AUTH_INVALID")
    if detail_level is not None and detail_level not in {"summary", "normal", "deep"}:
        raise BrainError("VALIDATION_FAILED")
    return {
        "request_id": request_id,
        "client_id": client_id,
        "operation": operation,
        "idempotency_key": idempotency_key,
        "requested_scope": requested_scope,
        "detail_level": detail_level,
        "expected_version": expected_version,
        "payload": dict(payload),
    }


def build_success_envelope(
    *,
    request_id: str,
    status: str,
    result: Mapping[str, Any],
    source_refs: list[str],
    warnings: list[str],
    audit_ref: str | None = None,
) -> dict[str, Any]:
    if status not in _ACCEPTED_STATUSES:
        raise BrainError("VALIDATION_FAILED")
    envelope: dict[str, Any] = {
        "request_id": request_id,
        "status": status,
        "result": dict(result),
        "source_refs": list(source_refs),
        "warnings": list(warnings),
    }
    if status == "completed":
        envelope["persistence"] = "canonical_committed"
    if audit_ref is not None:
        envelope["audit_ref"] = audit_ref
    return envelope


def build_error_envelope(
    *,
    request_id: str,
    error: Exception,
    correlation_id: str | None = None,
    audit_ref: str | None = None,
) -> dict[str, Any]:
    return safe_error(error, correlation_id=correlation_id or request_id, audit_ref=audit_ref)


@dataclass
class InMemoryOperationStatusStore:
    """In-memory `get_operation_status` lookup; persisted adapters replace it later.

    A mutation records ``accepted`` immediately and is later updated to
    ``completed``/``failed`` by the durable job or canonical commit boundary.
    """

    _records: dict[str, dict[str, Any]] = field(default_factory=dict)

    def record(self, operation_id: str, status: str, *, result: Mapping[str, Any] | None = None) -> None:
        if status not in _ACCEPTED_STATUSES | {"failed", "rejected"}:
            raise BrainError("VALIDATION_FAILED")
        self._records[operation_id] = {"status": status, "result": dict(result) if result else {}}

    def get(self, operation_id: str) -> dict[str, Any]:
        record = self._records.get(operation_id)
        if record is None:
            raise BrainError("NOT_FOUND")
        return dict(record)


class OperationStatusStore:
    """Owner-scoped durable status lookup; mutation status is recorded in UoW."""

    def __init__(self, repository: object) -> None:
        self._repository = repository

    def get(self, operation_id: str) -> dict[str, Any]:
        return self._repository.get_operation_status(uuid.UUID(operation_id))
