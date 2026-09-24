"""Append-only checkpoint capture.

FR-051: checkpoints append progress/problems/decisions/next-step/verification
evidence; prior checkpoints are never mutated.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Checkpoint:
    checkpoint_id: str
    task_id: object
    completed_work: str
    problems: str = ""
    decisions: tuple[str, ...] = ()
    next_step: str = ""
    verification_evidence: str = ""
    captured_at: datetime = None  # type: ignore[assignment]
    revision: str | None = None


def capture_checkpoint(*, task_id: object, completed_work: str, problems: str = "",
                       decisions: tuple[str, ...] = (), next_step: str = "",
                       verification_evidence: str = "", revision: str | None = None) -> Checkpoint:
    return Checkpoint(
        checkpoint_id=str(uuid.uuid4()),
        task_id=task_id,
        completed_work=completed_work,
        problems=problems,
        decisions=decisions,
        next_step=next_step,
        verification_evidence=verification_evidence,
        captured_at=datetime.now(timezone.utc),
        revision=revision,
    )