"""Todo lifecycle, archive semantics and deadline fields.

FR-014/FR-015/ER-04: pending and in_progress may complete directly; terminal
todos archive rather than silently delete; reopening a terminal todo is a
versioned correction that appends history instead of erasing it.
"""

from __future__ import annotations

from dataclasses import dataclass

from personal_brain_domain.common.errors import BrainError

_ALLOWED = frozenset({"pending", "in_progress", "completed", "cancelled"})
_TERMINAL = frozenset({"completed", "cancelled"})
_COMPLETABLE = frozenset({"pending", "in_progress"})


@dataclass(frozen=True)
class TodoState:
    state: str
    version: int
    previous_state: str | None = None
    correction_reason: str | None = None


def transition_todo(*, state: str, target_state: str, version: int, expected_version: int) -> TodoState:
    if state not in _ALLOWED or target_state not in _ALLOWED:
        raise ValueError("unknown todo state")
    if expected_version != version:
        raise BrainError("VERSION_CONFLICT")
    if target_state == "completed" and state not in _COMPLETABLE:
        raise BrainError("VALIDATION_FAILED")
    if state in _TERMINAL:
        raise BrainError("VALIDATION_FAILED")  # terminal needs a correction event
    return TodoState(state=target_state, version=version + 1)


def correct_terminal_todo(*, state: str, target_state: str, version: int, expected_version: int, reason: str) -> TodoState:
    if state not in _TERMINAL or target_state not in {"pending", "in_progress"}:
        raise BrainError("VALIDATION_FAILED")
    if expected_version != version:
        raise BrainError("VERSION_CONFLICT")
    return TodoState(state=target_state, version=version + 1, previous_state=state, correction_reason=reason)
