"""US10 Scenario K: durable-job crash/dead-letter and aggregate health (T137)."""

import pytest


def test_exhausted_failing_job_goes_dead_letter():
    from personal_brain_infra.jobs.store import JobPolicy, fail_job

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    engine = create_engine("sqlite+pysqlite:///:memory:")
    from sqlalchemy import Column, MetaData, String, Table, JSON
    from sqlalchemy import Integer as Int, DateTime

    metadata = MetaData()
    jobs = Table("jobs", metadata,
                 Column("id", String, primary_key=True), Column("owner_id", String, nullable=False),
                 Column("job_type", String, nullable=False), Column("payload_ref", String, nullable=False),
                 Column("state", String, nullable=False), Column("attempts", Int, nullable=False, default=0),
                 Column("max_attempts", Int, nullable=False, default=5),
                 Column("available_at", DateTime, nullable=False),
                 Column("lease_owner", String), Column("lease_expires_at", DateTime),
                 Column("claim_token", Int, nullable=False, default=0),
                 Column("started_at", DateTime), Column("finished_at", DateTime),
                 Column("error_code", String), Column("error_summary", String), Column("result_refs", JSON))
    metadata.create_all(engine)
    from datetime import datetime, timezone, timedelta

    with Session(engine) as session:
        session.execute(jobs.insert().values(id="j1", owner_id="o", job_type="embed", payload_ref="p",
                                             state="leased", attempts=5, max_attempts=5, available_at=datetime.now(timezone.utc),
                                             claim_token=3))
        session.commit()
    with Session(engine) as session:
        state = fail_job(session, jobs, job_id="j1", claim_token=3, error_code="X", error_summary="exhausted",
                         policy=JobPolicy(), now=datetime.now(timezone.utc), retryable=True)
        assert state == "dead_letter"
    engine.dispose()


def test_health_aggregates_without_collapsing_failures():
    from personal_brain_domain.operations.doctor import aggregate_health

    report = aggregate_health(components={"db": "healthy", "assets": "failed", "jobs": "degraded"})
    assert report["overall"] == "failed" or report["overall"] == "degraded"
    assert report["components"]["assets"] == "failed"
