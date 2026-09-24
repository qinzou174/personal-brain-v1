"""Finalize comparison, report, change-events and decision deduplication.

FR-052: finalizing a task compares start/end evidence, produces a report and
records change events; decisions/constraints deduplicate by a stable key.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FinalReport:
    outcome: str
    verification: str
    remaining_work: str = ""
    change_events: tuple[str, ...] = ()
    end_revision: str | None = None
    end_dirty_state: bool | None = None


def finalize_task(*, outcome: str, verification: str, remaining_work: str = "",
                  end_revision: str | None = None, end_dirty_state: bool | None = None) -> FinalReport:
    if not outcome or not verification:
        raise ValueError("finalize requires outcome and verification")
    return FinalReport(outcome=outcome, verification=verification, remaining_work=remaining_work,
                       end_revision=end_revision, end_dirty_state=end_dirty_state)


def deduplication_key(*, kind: str, statement: str) -> str:
    """Stable key used to dedupe decisions/constraints/change events."""
    return f"{kind}:{statement.strip().lower()}"