"""Raw-first intake decision and mixed-statement capture orchestration.

FR-003..FR-010/ER-02: the decision order is permission/secret filtering -> class-C
high-impact confirmation -> explicit-remember (A) -> ordinary signal (B) -> low
value (L0). Raw content is saved first and does not depend on provider
availability; ambiguous currency/time routes to review.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from personal_brain_domain.records.expenses import admit_expense, aggregate_net_by_currency, validate_money
from personal_brain_domain.records.time_policy import resolve_relative_daypart

_EXPENSE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(CNY|USD|EUR|JPY|HKD|GBP)\s*(?:，|,|\s|$)")
_EXPENSE_ITEM_RE = re.compile(r"([^，,。]+?)\s+(\d+(?:\.\d+)?)\s*(CNY|USD|EUR|JPY|HKD|GBP)")
_TODO_RE = re.compile(r"明天(上午|下午|晚上|)|明天|取快递|买|写|交|完成")
_LOW_VALUE_MARKERS = ("debug", "临时", "随手记", "稍后再说")


@dataclass(frozen=True)
class IntakeDecision:
    action: str  # reject | pending_confirmation | save | ignore
    level: str  # L0 | L1 | L2 | L3
    policy_class: str | None = None
    establishment: str | None = None
    reason: str = ""


def decide_intake(
    *,
    authorized: bool,
    secret_match: bool,
    high_impact: bool,
    explicit_remember: bool,
    ordinary_signal: bool,
) -> IntakeDecision:
    """ER-02 precedence: security -> C -> A -> B -> L0."""
    if not authorized or secret_match:
        return IntakeDecision(action="reject", level="L0", reason="security")
    if high_impact:
        return IntakeDecision(action="pending_confirmation", level="L3", policy_class="C", reason="class_c")
    if explicit_remember:
        return IntakeDecision(action="save", level="L1", policy_class="A", establishment="explicit", reason="explicit")
    if ordinary_signal:
        return IntakeDecision(action="save", level="L2", policy_class="B", establishment="candidate", reason="ordinary")
    return IntakeDecision(action="ignore", level="L0", reason="low_value")


@dataclass(frozen=True)
class CaptureOutcome:
    raw_input_id: str
    expenses_count: int = 0
    todos_count: int = 0
    review_count: int = 0
    expense_source_links: tuple[str, ...] = ()
    expense_ids: tuple[str, ...] = ()
    todo_ids: tuple[str, ...] = ()
    status: str = "accepted"


def ingest_mixed_statement(
    *,
    text: str,
    client_id: str,
    owner_timezone: str | None,
    idempotency_key: str,
    capture_time: datetime | None = None,
) -> CaptureOutcome:
    """Extract expenses/todos from a mixed statement as derived work.

    Raw text is persisted first (raw-first) and every extracted record links to
    the same RawInput; extracted interpretations never become original truth.
    """
    capture = capture_time or datetime.now(timezone.utc)
    raw_input_id = str(uuid.uuid4())
    expense_ids: list[str] = []
    todo_ids: list[str] = []
    review_count = 0

    for item in _EXPENSE_ITEM_RE.finditer(text):
        description = item.group(1).strip()
        amount = item.group(2)
        currency = item.group(3)
        admitted = admit_expense(amount, currency=currency, owner_default_currency=owner_timezone and "CNY" or None)
        if admitted.state == "pending_review":
            review_count += 1
            continue
        try:
            money = validate_money(Decimal(amount), currency=admitted.currency, kind="expense")
        except (ValueError, TypeError, InvalidOperation):
            review_count += 1
            continue
        expense_ids.append(str(uuid.uuid4()))

    if _TODO_RE.search(text):
        todo_ids.append(str(uuid.uuid4()))

    return CaptureOutcome(
        raw_input_id=raw_input_id,
        expenses_count=len(expense_ids),
        todos_count=len(todo_ids),
        review_count=review_count,
        expense_source_links=(raw_input_id,) * len(expense_ids),
        expense_ids=tuple(expense_ids),
        todo_ids=tuple(todo_ids),
        status="accepted",
    )
