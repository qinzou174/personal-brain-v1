"""Ordered idempotent retry and authoritative-outcome reconciliation.

FR-011/FR-088: replaying an operation multiple times yields exactly one
authoritative outcome; conflicts surface rather than being silently resolved.
"""

from __future__ import annotations

from dataclasses import dataclass


def reconcile_once(*, operation_id: str, attempts: tuple[str, ...]) -> tuple[str, ...]:
    """Return the single authoritative outcome from replayed attempts."""
    unique = tuple(dict.fromkeys(attempts))
    if len(unique) != 1:
        raise ValueError("conflicting replay outcomes require review")
    return unique


@dataclass(frozen=True)
class ReconciliationResult:
    operation_id: str
    outcome: object
    replayed_count: int = 0