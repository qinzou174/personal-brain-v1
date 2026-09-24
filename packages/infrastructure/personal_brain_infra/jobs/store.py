"""Durable job claim, lease, retry and dead-letter semantics.

ER-07: lease 60s, heartbeat 20s, at most 5 attempts including the first, delays
5/30/120/600s with <=20% jitter, then dead-letter. ``claim_token`` increases
monotonically on every claim so a worker holding a stale token can never commit
its result after the job was reclaimed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from personal_brain_domain.common.errors import BrainError


@dataclass(frozen=True)
class JobPolicy:
    lease_seconds: int = 60
    heartbeat_seconds: int = 20
    max_attempts: int = 5
    retry_base_seconds: tuple[int, ...] = (5, 30, 120, 600)
    jitter_fraction: float = 0.20

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 5:
            raise ValueError("max_attempts must be between 1 and 5")
        if len(self.retry_base_seconds) != self.max_attempts - 1:
            raise ValueError("retry schedule must have max_attempts - 1 delays")
        if not 0.0 <= self.jitter_fraction <= 0.25:
            raise ValueError("jitter_fraction must be between 0 and 0.25")

    def next_delay(self, *, attempt: int, jitter: float = 0.0) -> float:
        """Delay in seconds for the retry after ``attempt`` (1-based)."""
        if attempt < 1:
            raise ValueError("attempt must be at least 1")
        base = self.retry_base_seconds[min(attempt, len(self.retry_base_seconds)) - 1]
        factor = 1.0 + self.jitter_fraction * max(-1.0, min(1.0, jitter))
        return base * factor

    def retry_available_at(self, *, attempt: int, now: datetime, jitter: float = 0.0) -> datetime:
        return now + timedelta(seconds=self.next_delay(attempt=attempt, jitter=jitter))


def may_commit_result(*, state: str, submitted_claim_token: int, current_claim_token: int) -> bool:
    """A result may be committed only by the current lease holder."""
    return state == "leased" and submitted_claim_token == current_claim_token


def claim_ready_jobs(
    session: Any,
    table: Any,
    *,
    owner_id: str,
    worker_id: str,
    policy: JobPolicy,
    now: datetime,
    batch_size: int = 10,
    jitter: float = 0.0,
) -> list[dict[str, Any]]:
    """Atomically claim ready jobs, including leases abandoned by crashed workers.

    Each claim advances ``claim_token`` and lease fields so a reclaimed job's
    previous worker cannot commit stale results. Rows are updated with a
    monotonic token under the unique idempotency key, preventing double claim.
    """
    from sqlalchemy import select, update

    ready = (
        (table.c.state.in_(("queued", "retry_wait")) & (table.c.available_at <= now))
        | ((table.c.state == "leased") & (table.c.lease_expires_at <= now))
    )

    candidates = session.execute(
        select(table).where(
            table.c.owner_id == owner_id,
            ready,
        )
        .order_by(table.c.priority.desc(), table.c.available_at)
        .limit(batch_size)
    ).mappings().all()

    claimed: list[dict[str, Any]] = []
    for row in candidates:
        if int(row["attempts"]) >= min(int(row["max_attempts"]), policy.max_attempts):
            session.execute(
                update(table)
                .where(table.c.id == row["id"], table.c.claim_token == row["claim_token"],
                       table.c.state == row["state"], ready)
                .values(state="dead_letter", finished_at=now, lease_owner=None,
                        lease_expires_at=None, error_code="BRAIN_UNAVAILABLE",
                        error_summary="job lease expired after maximum attempts")
            )
            continue
        new_token = int(row["claim_token"]) + 1
        new_attempts = int(row["attempts"]) + 1
        result = session.execute(
            update(table)
            .where(table.c.id == row["id"], table.c.claim_token == row["claim_token"],
                   table.c.state == row["state"], ready)
            .values(
                state="leased",
                attempts=new_attempts,
                lease_owner=worker_id,
                lease_expires_at=now + timedelta(seconds=policy.lease_seconds),
                claim_token=new_token,
                started_at=now,
            )
        )
        if result.rowcount != 1:
            continue  # another worker claimed it first; keep the winner
        claimed.append(dict(row, state="leased", attempts=new_attempts, claim_token=new_token,
                            lease_owner=worker_id, lease_expires_at=now + timedelta(seconds=policy.lease_seconds)))
    return claimed


def heartbeat_job(
    session: Any,
    table: Any,
    *,
    job_id: str,
    worker_id: str,
    claim_token: int,
    policy: JobPolicy,
    now: datetime,
) -> bool:
    """Renew a lease only while the caller still holds the current token."""
    from sqlalchemy import update

    result = session.execute(
        update(table)
        .where(
            table.c.id == job_id,
            table.c.lease_owner == worker_id,
            table.c.claim_token == claim_token,
            table.c.state == "leased",
        )
        .values(lease_expires_at=now + timedelta(seconds=policy.lease_seconds))
    )
    return result.rowcount == 1


def update_job_progress(
    session: Any, table: Any, *, job_id: str, claim_token: int,
    progress: int, summary: str,
) -> bool:
    """Persist bounded progress under the current fencing token."""
    if not 0 <= progress <= 100 or len(summary) > 256:
        raise ValueError("invalid job progress")
    from sqlalchemy import update

    result = session.execute(
        update(table).where(
            table.c.id == job_id, table.c.claim_token == claim_token, table.c.state == "leased",
        ).values(result_refs={"progress": progress, "summary": summary})
    )
    return result.rowcount == 1


def complete_job(
    session: Any,
    table: Any,
    *,
    job_id: str,
    claim_token: int,
    result_refs: Any,
    now: datetime,
) -> bool:
    """Record a successful, idempotent result under fencing."""
    from sqlalchemy import update

    result = session.execute(
        update(table)
        .where(table.c.id == job_id, table.c.claim_token == claim_token, table.c.state == "leased")
        .values(state="succeeded", finished_at=now, result_refs=result_refs)
    )
    return result.rowcount == 1


def fail_job(
    session: Any,
    table: Any,
    *,
    job_id: str,
    claim_token: int,
    error_code: str,
    error_summary: str,
    policy: JobPolicy,
    now: datetime,
    retryable: bool,
    jitter: float = 0.0,
) -> str:
    """Move a failed job to retry_wait or dead_letter.

    Non-retryable failures (validation, permission, secret) go straight to
    dead_letter. Retryable failures schedule the next attempt until exhausted.
    """
    from sqlalchemy import select, update

    row = session.execute(select(table).where(table.c.id == job_id)).mappings().one_or_none()
    if row is None:
        raise BrainError("NOT_FOUND")
    attempts = int(row["attempts"])
    if not retryable or attempts >= policy.max_attempts:
        session.execute(
            update(table)
            .where(table.c.id == job_id, table.c.claim_token == claim_token)
            .values(state="dead_letter", finished_at=now, error_code=error_code, error_summary=error_summary)
        )
        return "dead_letter"
    available_at = policy.retry_available_at(attempt=attempts, now=now, jitter=jitter)
    session.execute(
        update(table)
        .where(table.c.id == job_id, table.c.claim_token == claim_token)
        .values(
            state="retry_wait",
            available_at=available_at,
            lease_owner=None,
            lease_expires_at=None,
            error_code=error_code,
            error_summary=error_summary,
        )
    )
    return "retry_wait"
