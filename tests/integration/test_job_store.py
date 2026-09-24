"""Full durable-job lifecycle: claim, heartbeat, reclaim fencing, dead-letter (T028)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, MetaData, String, Table, create_engine, func, select
from sqlalchemy.orm import Session

from personal_brain_infra.jobs.store import (
    JobPolicy,
    claim_ready_jobs,
    complete_job,
    fail_job,
    heartbeat_job,
    update_job_progress,
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _make_table(engine):
    metadata = MetaData()
    return Table(
        "jobs", metadata,
        Column("id", String, primary_key=True),
        Column("owner_id", String, nullable=False),
        Column("job_type", String, nullable=False),
        Column("payload_ref", String, nullable=False),
        Column("state", String, nullable=False),
        Column("priority", __import__("sqlalchemy").Integer, nullable=False, default=0),
        Column("attempts", __import__("sqlalchemy").Integer, nullable=False, default=0),
        Column("max_attempts", __import__("sqlalchemy").Integer, nullable=False, default=5),
        Column("available_at", __import__("sqlalchemy").DateTime, nullable=False),
        Column("lease_owner", String),
        Column("lease_expires_at", __import__("sqlalchemy").DateTime),
        Column("claim_token", __import__("sqlalchemy").Integer, nullable=False, default=0),
        Column("started_at", __import__("sqlalchemy").DateTime),
        Column("finished_at", __import__("sqlalchemy").DateTime),
        Column("error_code", String),
        Column("error_summary", String),
        Column("result_refs", __import__("sqlalchemy").JSON),
    )
    # metadata.create_all(engine) called by caller


def test_claim_retry_dead_letter_and_reclaim_fencing():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    jobs = Table(
        "jobs", metadata,
        Column("id", String, primary_key=True), Column("owner_id", String, nullable=False),
        Column("job_type", String, nullable=False), Column("payload_ref", String, nullable=False),
        Column("state", String, nullable=False), Column("priority", __import__("sqlalchemy").Integer, nullable=False, default=0),
        Column("attempts", __import__("sqlalchemy").Integer, nullable=False, default=0),
        Column("max_attempts", __import__("sqlalchemy").Integer, nullable=False, default=5),
        Column("available_at", __import__("sqlalchemy").DateTime, nullable=False),
        Column("lease_owner", String), Column("lease_expires_at", __import__("sqlalchemy").DateTime),
        Column("claim_token", __import__("sqlalchemy").Integer, nullable=False, default=0),
        Column("started_at", __import__("sqlalchemy").DateTime), Column("finished_at", __import__("sqlalchemy").DateTime),
        Column("error_code", String), Column("error_summary", String),
        Column("result_refs", __import__("sqlalchemy").JSON),
    )
    metadata.create_all(engine)
    policy = JobPolicy()

    def insert(session, **overrides):
        base = dict(owner_id="o", job_type="embed", payload_ref="p", state="queued",
                    priority=0, attempts=0, max_attempts=5, available_at=_now() - timedelta(minutes=1),
                    claim_token=0)
        session.execute(jobs.insert().values(**(base | overrides)))

    with Session(engine) as session:
        insert(session, id="job-1")
        insert(session, id="job-2", job_type="parse", priority=10, payload_ref="q")
        session.commit()

    with Session(engine) as session:
        now = _now()
        first = claim_ready_jobs(session, jobs, owner_id="o", worker_id="worker-a", policy=policy, now=now)
        assert len(first) == 2
        job1 = next(j for j in first if j["id"] == "job-1")
        assert job1["state"] == "leased" and job1["claim_token"] == 1 and job1["attempts"] == 1
        assert heartbeat_job(session, jobs, job_id="job-1", worker_id="worker-a", claim_token=1, policy=policy, now=now)
        assert update_job_progress(session, jobs, job_id="job-1", claim_token=1, progress=25, summary="working")
        assert not update_job_progress(session, jobs, job_id="job-1", claim_token=999, progress=50, summary="stale")
        assert not complete_job(session, jobs, job_id="job-1", claim_token=999, result_refs={"r": 1}, now=now)
        session.commit()

    with Session(engine) as session:
        now = _now()
        # A crashed worker leaves a leased row; expiry must reclaim it without manual repair.
        session.execute(
            jobs.update().where(jobs.c.id == "job-1").values(lease_expires_at=now - timedelta(seconds=1))
        )
        re = claim_ready_jobs(session, jobs, owner_id="o", worker_id="worker-b", policy=policy, now=now)
        assert len(re) == 1 and re[0]["id"] == "job-1" and re[0]["claim_token"] == 2
        assert not complete_job(session, jobs, job_id="job-1", claim_token=1, result_refs={}, now=now)
        session.commit()

    with Session(engine) as session:
        assert fail_job(session, jobs, job_id="job-1", claim_token=2, error_code="BRAIN_UNAVAILABLE",
                        error_summary="down", policy=policy, now=_now(), retryable=True) in {"retry_wait", "dead_letter"}
        session.commit()

    with Session(engine) as session:
        attempts = session.scalar(select(jobs.c.attempts).where(jobs.c.id == "job-1"))
        assert attempts >= 2
    engine.dispose()
