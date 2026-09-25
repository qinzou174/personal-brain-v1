"""Exact Expense rules, currencies, refunds/adjustments and aggregation.

FR-012/FR-013/ER-04: amount is exact numeric(20,4) and strictly positive for an
expense; a refund is positive but typed, and net totals never combine different
currencies without an explicit conversion basis. Corrections append a prior
version instead of mutating the original.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Mapping

from personal_brain_domain.common.errors import BrainError

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_KINDS = frozenset({"expense", "refund", "adjustment"})


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str
    kind: str
    category: str = "uncategorized"
    description: str = ""
    occurred_at: object | None = None
    occurred_timezone: str | None = None
    event_id: object | None = None
    source_id: object | None = None
    version: int = 1
    previous: "Money | None" = None
    used_owner_default: bool = False


@dataclass(frozen=True)
class AdmittedExpense:
    amount: Decimal
    currency: str | None
    state: str
    used_owner_default: bool = False


def validate_money(amount, *, currency, kind="expense") -> Money:
    """Validate exact money; Decimal required, positive for expense/refund.

    Boundary violations raise the stable in-band ``VALIDATION_FAILED`` (not a
    bare ValueError): the HTTP layer maps a leaking ValueError to a -32700
    transport parse error with a lost request id, which told clients nothing
    about what was actually wrong (B-01, SIMTEST S-13).
    """
    if kind not in _KINDS:
        raise BrainError("VALIDATION_FAILED")
    if not isinstance(currency, str) or not _CURRENCY_RE.match(currency):
        raise BrainError("VALIDATION_FAILED")
    if isinstance(amount, float) or not isinstance(amount, Decimal):
        raise TypeError("amount must be a Decimal, not a binary float")
    if not amount.is_finite():
        raise BrainError("VALIDATION_FAILED")
    if -amount.as_tuple().exponent > 4 or amount.as_tuple().exponent > 0:
        raise BrainError("VALIDATION_FAILED")
    exponent = amount.as_tuple().exponent
    if amount == amount.to_integral_value():
        integer_digits = len(amount.as_tuple().digits)
    else:
        digits = amount.as_tuple().digits
        integer_digits = len(digits) + exponent
    if integer_digits > 16:
        raise BrainError("VALIDATION_FAILED")
    if amount <= 0:
        raise BrainError("VALIDATION_FAILED")
    return Money(amount=amount, currency=currency, kind=kind)


def admit_expense(amount, *, currency, owner_default_currency=None, category="uncategorized", description="") -> AdmittedExpense:
    """Route missing-currency intake: owner default accepts, otherwise review."""
    if currency is None:
        if owner_default_currency and _CURRENCY_RE.match(owner_default_currency):
            return AdmittedExpense(amount=amount, currency=owner_default_currency, state="accepted", used_owner_default=True)
        return AdmittedExpense(amount=amount, currency=None, state="pending_review")
    return AdmittedExpense(amount=amount, currency=currency, state="accepted")


def aggregate_net_by_currency(entries: list[Money]) -> dict[str, Decimal]:
    """Exact per-currency net; refunds/adjustments subtract, never cross-currency."""
    totals: dict[str, Decimal] = {}
    for entry in entries:
        delta = entry.amount if entry.kind == "expense" else -entry.amount
        totals[entry.currency] = totals.get(entry.currency, Decimal("0.0000")) + delta
    return totals


def correct_expense(original: Mapping[str, object], *, new_amount: Decimal, expected_version: int) -> Money:
    """Versioned correction: prior version retained, original never mutated."""
    if expected_version != original["version"]:
        raise BrainError("VERSION_CONFLICT")
    prior = Money(
        amount=original["amount"],
        currency=str(original["currency"]),
        kind="expense",
        version=int(original["version"]),
    )
    return Money(
        amount=new_amount,
        currency=str(original["currency"]),
        kind="adjustment",
        version=int(original["version"]) + 1,
        previous=prior,
    )
