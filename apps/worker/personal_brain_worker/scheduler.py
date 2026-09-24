"""Lightweight in-worker cron: periodic durable jobs for a living backend.

Δ1: the worker used to execute only event-driven jobs (one per user action), so
digest, promotion, retention and conflict review never ran at all.  This
component enqueues one durable job per schedule and local day, using the jobs
table itself as the idempotency record: the queue key is a deterministic
``uuid5`` of owner + job type + local-day bucket, so repeated ticks or a second
worker can never double-enqueue the same day.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5
from zoneinfo import ZoneInfo

import sqlalchemy as sa


@dataclass(frozen=True)
class DailySchedule:
    """One local-time daily job (hour/minute are wall-clock in the owner timezone)."""

    job_type: str
    hour: int
    minute: int

    def __post_init__(self) -> None:
        if not self.job_type:
            raise ValueError("daily schedule requires a job type")
        if not 0 <= self.hour <= 23 or not 0 <= self.minute <= 59:
            raise ValueError("daily schedule time is invalid")


# Digest runs early morning for the previous day; evolution after it; dedupe last
# (D2: after the day's promotion and conflict pass, duplicates are merged and
# suspected pairs become one merge_candidate review item); health last.
DEFAULT_SCHEDULES: tuple[DailySchedule, ...] = (
    DailySchedule("daily_digest", 3, 10),
    DailySchedule("promote_candidates", 4, 10),
    DailySchedule("retention_sweep", 4, 20),
    DailySchedule("conflict_scan", 4, 30),
    DailySchedule("retention_maintenance", 4, 40),
    DailySchedule("dedupe_claims", 4, 50),
    DailySchedule("health_check", 8, 0),
)


def to_local(now_utc: datetime, timezone_name: str) -> datetime:
    return now_utc.astimezone(ZoneInfo(timezone_name))


def schedule_bucket(*, local_now: datetime) -> str:
    """The idempotency bucket of a schedule: one local calendar day."""
    return local_now.date().isoformat()


def schedule_due(schedule: DailySchedule, *, local_now: datetime) -> bool:
    return (local_now.hour, local_now.minute) >= (schedule.hour, schedule.minute)


def schedule_key(*, owner_id: UUID, job_type: str, bucket: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"brain-schedule:{owner_id}:{job_type}:{bucket}")


class PeriodicScheduler:
    """Enqueue due daily jobs for every owner exactly once per local day."""

    def __init__(
        self, session_factory: Any, tables: Mapping[str, sa.Table], *,
        schedules: tuple[DailySchedule, ...] = DEFAULT_SCHEDULES,
        timezone_name: str = "Asia/Shanghai",
        now: Callable[[], datetime] | None = None,
        tick_seconds: float = 60.0,
    ) -> None:
        missing = {"owners", "jobs"}.difference(tables)
        if missing:
            raise RuntimeError(f"schedule schema missing tables: {sorted(missing)}")
        self._factory = session_factory
        self._owners = tables["owners"]
        self._jobs = tables["jobs"]
        self._schedules = tuple(schedules)
        self._timezone = timezone_name
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._tick_seconds = tick_seconds
        self._last_tick: datetime | None = None

    def tick(self) -> int:
        """Enqueue due jobs; returns how many were newly enqueued."""
        now = self._now()
        if self._last_tick is not None and (now - self._last_tick).total_seconds() < self._tick_seconds:
            return 0
        self._last_tick = now
        local_now = to_local(now, self._timezone)
        due = [schedule for schedule in self._schedules
               if schedule_due(schedule, local_now=local_now)]
        if not due:
            return 0
        bucket = schedule_bucket(local_now=local_now)
        enqueued = 0
        with self._factory.begin() as session:
            owner_ids = session.scalars(sa.select(self._owners.c.id).distinct()).all()
            for owner_id in owner_ids:
                for schedule in due:
                    key = schedule_key(owner_id=owner_id, job_type=schedule.job_type, bucket=bucket)
                    if session.get_bind().dialect.name == "postgresql":
                        # Serialize concurrent schedulers on the same queue key.
                        session.execute(
                            sa.text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": str(key)},
                        )
                    already = session.scalar(sa.select(sa.func.count()).select_from(self._jobs).where(
                        self._jobs.c.owner_id == owner_id,
                        self._jobs.c.idempotency_key == key,
                    ))
                    if already:
                        continue
                    session.execute(self._jobs.insert().values(
                        id=uuid4(), owner_id=owner_id, client_id=None,
                        job_type=schedule.job_type,
                        payload_ref=f"schedule:{schedule.job_type}:{bucket}",
                        idempotency_key=key, state="queued", priority=0, attempts=0,
                        max_attempts=5, available_at=now, claim_token=0,
                    ))
                    enqueued += 1
        return enqueued