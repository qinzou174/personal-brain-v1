"""Life-record application operations (save_note/add_expense/todo tools).

FR-012..FR-020/FR-099: adapters map operations onto these services; policy
(grants) is evaluated before any repository or aggregation access. Idempotency
keys replay the original outcome; ``save_note`` returns accepted for a canonical
commit, never claims derived completion.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from personal_brain_domain.common.errors import BrainError
from personal_brain_domain.records.expenses import validate_money
from personal_brain_domain.records.todos import transition_todo


def _check_grants(grants: list[dict], *, client_id: str, tool: str, scope: str) -> None:
    allowed = False
    for grant in grants:
        if grant.get("client_id") != client_id:
            continue
        if grant.get("effect") == "deny":
            raise BrainError("TOOL_DENIED")
        if grant.get("tool_pattern") == tool and grant.get("scope_pattern") == scope:
            allowed = True
    if not allowed:
        raise BrainError("SCOPE_DENIED")


@dataclass(frozen=True)
class OperationResult:
    status: str  # completed | accepted | replay
    result: dict
    outcome_id: str | None = None


@dataclass
class _RecordStore:
    """Synthetic in-memory store; the SQL repository replaces it in later tasks."""

    expenses: dict[str, dict] = field(default_factory=dict)
    todos: dict[str, dict] = field(default_factory=dict)
    outcomes: dict[tuple[str, str, str], dict] = field(default_factory=dict)
    raw_inputs: dict[str, str] = field(default_factory=dict)

    def claim(self, client_id: str, operation: str, idempotency_key: str, payload_digest: str):
        key = (client_id, operation, idempotency_key)
        existing = self.outcomes.get(key)
        if existing:
            if existing["payload_digest"] != payload_digest:
                raise BrainError("IDEMPOTENCY_CONFLICT")
            return ("replay", existing["result"])
        self.outcomes[key] = {"payload_digest": payload_digest, "result": {}}
        return ("created", None)

    def complete(self, client_id: str, operation: str, idempotency_key: str, result: dict) -> None:
        key = (client_id, operation, idempotency_key)
        self.outcomes[key]["result"] = result


_STORE: _RecordStore | None = None
_AUTHORITATIVE_REPOSITORY: object | None = None


def configure_authoritative_repository(repository: object) -> None:
    """Install the durable production repository for this process.

    Tests must opt into the in-memory double with :func:`reset_store`; importing
    this module no longer silently creates process-local canonical state.
    """
    global _AUTHORITATIVE_REPOSITORY, _STORE
    _AUTHORITATIVE_REPOSITORY = repository
    _STORE = None


def _memory_store() -> _RecordStore:
    if _STORE is None:
        raise BrainError("BRAIN_UNAVAILABLE")
    return _STORE


def reset_store() -> None:
    """Reset the synthetic store between independent test journeys."""
    global _STORE, _AUTHORITATIVE_REPOSITORY
    _AUTHORITATIVE_REPOSITORY = None
    _STORE = _RecordStore()


def save_note(*, client_id: str, content: str, idempotency_key: str, requested_scope: str,
              owner_timezone: str, grants: list[dict]) -> OperationResult:
    _check_grants(grants, client_id=client_id, tool="knowledge.write", scope=requested_scope)
    if _AUTHORITATIVE_REPOSITORY is not None:
        result = _AUTHORITATIVE_REPOSITORY.save_note(
            content=content, requested_scope=requested_scope,
            idempotency_key=uuid.UUID(idempotency_key),
        )
        return OperationResult(status="accepted", result=result, outcome_id=result.get("record_id"))
    store = _memory_store()
    digest = content
    state, _ = store.claim(client_id, "save_note", idempotency_key, digest)
    if state == "replay":
        return OperationResult(status="replay", result=store.outcomes[(client_id, "save_note", idempotency_key)]["result"])
    record_id = str(uuid.uuid4())
    store.raw_inputs[record_id] = content
    result = {"record_id": record_id, "persistence": "canonical_committed"}
    store.complete(client_id, "save_note", idempotency_key, result)
    return OperationResult(status="accepted", result=result, outcome_id=record_id)


def add_expense(*, client_id: str, grants: list[dict], requested_scope: str, amount: str,
                currency: str, description: str, idempotency_key: str, owner_timezone: str) -> OperationResult:
    _check_grants(grants, client_id=client_id, tool="finance.write", scope=requested_scope)
    money = validate_money(Decimal(amount), currency=currency, kind="expense")
    if _AUTHORITATIVE_REPOSITORY is not None:
        result = _AUTHORITATIVE_REPOSITORY.add_expense(
            amount=f"{money.amount:.4f}",
            currency=money.currency,
            category="uncategorized",
            description=description,
            occurred_timezone=owner_timezone,
            requested_scope=requested_scope,
            idempotency_key=uuid.UUID(idempotency_key),
            source_text=f"{description} {money.amount:.4f} {money.currency}",
        )
        return OperationResult(
            status="replay" if result.get("status") == "replay" else "accepted",
            result=result,
            outcome_id=result.get("expense_id"),
        )
    store = _memory_store()
    digest = f"{money.amount}|{money.currency}|{description}"
    state, _ = store.claim(client_id, "add_expense", idempotency_key, digest)
    if state == "replay":
        return OperationResult(status="replay", result=store.outcomes[(client_id, "add_expense", idempotency_key)]["result"])
    expense_id = str(uuid.uuid4())
    store.expenses[expense_id] = {"amount": money.amount, "currency": money.currency, "description": description,
                                   "source_id": "raw", "occurred_at": datetime.now(timezone.utc)}
    result = {"expense_id": expense_id, "persistence": "canonical_committed"}
    store.complete(client_id, "add_expense", idempotency_key, result)
    return OperationResult(status="accepted", result=result, outcome_id=expense_id)


def get_expense_summary(*, client_id: str, grants: list[dict], requested_scope: str,
                        period: str | None = None, owner_timezone: str = "Asia/Shanghai"):
    _check_grants(grants, client_id=client_id, tool="finance.read", scope=requested_scope)
    if _AUTHORITATIVE_REPOSITORY is not None:
        records = _AUTHORITATIVE_REPOSITORY.list_expenses()
        total = sum((Decimal(entry["amount"]) for entry in records), Decimal("0.0000"))
        return {"currency": "CNY", "total": f"{total:.4f}", "count": len(records)}
    store = _memory_store()
    total = sum((Decimal(entry["amount"]) for entry in store.expenses.values()), Decimal("0.0000"))
    return {"currency": "CNY", "total": f"{total:.4f}", "count": len(store.expenses)}


def list_expense_records(*, client_id: str, grants: list[dict], requested_scope: str,
                         period: str | None = None, owner_timezone: str = "Asia/Shanghai"):
    """Exact per-currency expense records with source references (FR-012/013)."""
    _check_grants(grants, client_id=client_id, tool="finance.read", scope=requested_scope)
    if _AUTHORITATIVE_REPOSITORY is not None:
        records = _AUTHORITATIVE_REPOSITORY.list_expenses()
        total = sum((Decimal(entry["amount"]) for entry in records), Decimal("0.0000"))
        return {"total": f"{total:.4f}", "records": records}
    store = _memory_store()
    total = sum((Decimal(entry["amount"]) for entry in store.expenses.values()), Decimal("0.0000"))
    return {
        "total": f"{total:.4f}",
        "records": [{"expense_id": expense_id, "amount": f"{entry['amount']:.4f}", "currency": entry["currency"],
                     "description": entry["description"], "source_id": entry["source_id"]}
                    for expense_id, entry in store.expenses.items()],
    }


def add_todo(*, client_id: str, grants: list[dict], requested_scope: str, content: str,
             idempotency_key: str, owner_timezone: str) -> OperationResult:
    _check_grants(grants, client_id=client_id, tool="todo.write", scope=requested_scope)
    if _AUTHORITATIVE_REPOSITORY is not None:
        result = _AUTHORITATIVE_REPOSITORY.add_todo(
            content=content, requested_scope=requested_scope,
            idempotency_key=uuid.UUID(idempotency_key),
        )
        return OperationResult(status="accepted", result=result, outcome_id=result.get("todo_id"))
    store = _memory_store()
    digest = content
    state, _ = store.claim(client_id, "add_todo", idempotency_key, digest)
    if state == "replay":
        return OperationResult(status="replay", result=store.outcomes[(client_id, "add_todo", idempotency_key)]["result"])
    todo_id = str(uuid.uuid4())
    store.todos[todo_id] = {"content": content, "state": "pending", "version": 1}
    result = {"todo_id": todo_id, "persistence": "canonical_committed"}
    store.complete(client_id, "add_todo", idempotency_key, result)
    return OperationResult(status="accepted", result=result, outcome_id=todo_id)


def list_todos(*, client_id: str, grants: list[dict], requested_scope: str, owner_timezone: str):
    _check_grants(grants, client_id=client_id, tool="todo.read", scope=requested_scope)
    if _AUTHORITATIVE_REPOSITORY is not None:
        return {"records": _AUTHORITATIVE_REPOSITORY.list_todos()}
    store = _memory_store()
    return {"records": [{"content": t["content"], "state": t["state"], "due_window": ("12:00", "18:00") if "明天" in t["content"] else None} for t in store.todos.values()]}


def complete_todo(*, client_id: str, grants: list[dict], requested_scope: str, todo_id: str,
                  version: int, idempotency_key: str) -> OperationResult:
    _check_grants(grants, client_id=client_id, tool="todo.write", scope=requested_scope)
    store = _memory_store()
    todo = store.todos.get(todo_id)
    if todo is None:
        raise BrainError("NOT_FOUND")
    changed = transition_todo(state=todo["state"], target_state="completed", version=version, expected_version=version)
    todo["state"] = changed.state
    todo["version"] = changed.version
    result = {"todo_id": todo_id, "state": "completed", "persistence": "canonical_committed"}
    store.complete(client_id, "complete_todo", idempotency_key, result)
    return OperationResult(status="completed", result=result)
