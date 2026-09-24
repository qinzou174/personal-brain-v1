"""Background LLM budget: one per-local-day job quota for derivation jobs.

D1(b): background derivation is bounded by a *daily* budget (default 200 jobs)
instead of the per-call cap, so the backend can stay alive without unbounded
cost.  The jobs table is the meter: every LLM-using job counts once per lease
(``started_at`` is set when a worker claims it), so retries are counted honestly.
Exceeding the quota degrades the affected job to rules-only behavior and never
blocks canonical writes.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import sqlalchemy as sa

LLM_JOB_TYPES = ("extract_raw_input", "daily_digest")


def day_window(now_utc: datetime, timezone_name: str) -> tuple[datetime, datetime]:
    """The current local calendar day as a half-open UTC interval."""
    local = now_utc.astimezone(ZoneInfo(timezone_name))
    start = local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(ZoneInfo("UTC"))
    return start, start + timedelta(days=1)


def llm_jobs_started(
    session: Any, jobs: sa.Table, *, owner_id: Any, now_utc: datetime, timezone_name: str,
) -> int:
    start, end = day_window(now_utc, timezone_name)
    return int(session.scalar(sa.select(sa.func.count()).select_from(jobs).where(
        jobs.c.owner_id == owner_id,
        jobs.c.job_type.in_(LLM_JOB_TYPES),
        jobs.c.started_at.is_not(None),
        jobs.c.started_at >= start,
        jobs.c.started_at < end,
    )) or 0)


def quota_exceeded(
    session: Any, jobs: sa.Table, *, owner_id: Any, now_utc: datetime,
    timezone_name: str, quota: int,
) -> bool:
    """True when this lease would exceed the owner's daily LLM job budget."""
    if quota < 1:
        raise ValueError("llm quota must be positive")
    return llm_jobs_started(
        session, jobs, owner_id=owner_id, now_utc=now_utc, timezone_name=timezone_name,
    ) > quota