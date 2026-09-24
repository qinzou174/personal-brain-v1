"""Δ1: the periodic scheduler turns event-driven work into a living loop.

The scheduler must enqueue one durable job per schedule and local day, never
duplicate an already-enqueued bucket, and stay silent before the local due time.
"""

from __future__ import annotations

import sqlalchemy as sa
import pytest

from activation_support import build_harness, local_at, seed_owner


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    h = build_harness(tmp_path_factory)
    yield h
    h.drop_schema()


def _jobs(harness, owner_id) -> list[dict]:
    with harness.factory() as session:
        return [dict(row) for row in session.execute(sa.select(harness.tables["jobs"]).where(
            harness.tables["jobs"].c.owner_id == owner_id,
        )).mappings().all()]


def _scheduler(harness, fixed_utc, **kwargs):
    from personal_brain_worker.scheduler import PeriodicScheduler

    return PeriodicScheduler(
        harness.factory, harness.tables, timezone_name="Asia/Shanghai",
        now=lambda: fixed_utc, tick_seconds=0, **kwargs,
    )


def test_scheduler_enqueues_each_daily_job_once_per_local_day(harness):
    from personal_brain_worker.scheduler import DEFAULT_SCHEDULES

    owner_id, _client_id = seed_owner(harness)
    morning = _scheduler(harness, local_at(2026, 9, 21, 9, 0))
    assert morning.tick() == len(DEFAULT_SCHEDULES)
    rows = _jobs(harness, owner_id)
    assert {row["job_type"] for row in rows} == {schedule.job_type for schedule in DEFAULT_SCHEDULES}
    assert all(row["state"] == "queued" and row["client_id"] is None for row in rows)
    assert all(row["payload_ref"].startswith("schedule:") for row in rows)

    # Same bucket: a second tick must not enqueue anything again.
    assert morning.tick() == 0
    assert len(_jobs(harness, owner_id)) == len(DEFAULT_SCHEDULES)

    # A second worker instance must also respect the bucket idempotency.
    assert _scheduler(harness, local_at(2026, 9, 21, 23, 0)).tick() == 0

    # The next local day opens a fresh bucket.
    next_day = _scheduler(harness, local_at(2026, 9, 22, 9, 0))
    assert next_day.tick() == len(DEFAULT_SCHEDULES)
    assert len(_jobs(harness, owner_id)) == 2 * len(DEFAULT_SCHEDULES)


def test_scheduler_stays_silent_before_local_due_time(harness):
    owner_id, _client_id = seed_owner(harness)
    early = _scheduler(harness, local_at(2026, 9, 23, 2, 0))
    assert early.tick() == 0
    assert _jobs(harness, owner_id) == []
    # 03:10 local opens only the first schedule of the day, for every owner.
    assert _scheduler(harness, local_at(2026, 9, 23, 3, 15)).tick() >= 1
    assert {row["job_type"] for row in _jobs(harness, owner_id)} == {"daily_digest"}


def test_scheduler_serves_every_owner(harness):
    from personal_brain_worker.scheduler import DEFAULT_SCHEDULES

    first_owner, _ = seed_owner(harness)
    second_owner, _ = seed_owner(harness)
    assert _scheduler(harness, local_at(2026, 9, 24, 9, 0)).tick() >= 2 * len(DEFAULT_SCHEDULES)
    for owner_id in (first_owner, second_owner):
        rows = _jobs(harness, owner_id)
        assert len(rows) == len(DEFAULT_SCHEDULES)
        assert {row["job_type"] for row in rows} == {schedule.job_type for schedule in DEFAULT_SCHEDULES}
    # Later the same day every owner is already covered.
    assert _scheduler(harness, local_at(2026, 9, 24, 23, 0)).tick() == 0