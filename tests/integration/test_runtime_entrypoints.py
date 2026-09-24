"""T172: runtime entrypoints are long-running, observable, and fail closed."""

from __future__ import annotations

import io
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from fastapi.testclient import TestClient


def test_server_health_is_live_while_readiness_reflects_dependencies():
    from personal_brain_server.runtime import create_app

    app = create_app(readiness_probe=lambda: {
        "ready": False, "database": "ok", "worker": "failed", "storage": "ok",
    })
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "alive"}
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json()["worker"] == "failed"


def test_doctor_cli_reports_missing_configuration_as_json(monkeypatch, capsys):
    from personal_brain_server.__main__ import main

    for name in ("BRAIN_DATA_ROOT", "BRAIN_DATABASE_DSN_FILE", "BRAIN_TOKEN_PEPPER_FILE"):
        monkeypatch.delenv(name, raising=False)
    assert main(["doctor", "--preflight", "--json"]) == 2
    report = __import__("json").loads(capsys.readouterr().out)
    assert report["ready"] is False
    assert report["configuration"] == "failed"
    assert set(report["missing_fields"]) == {
        "data_root", "database_dsn_file", "token_pepper_file",
    }
    assert "input" not in report and "url" not in report


def test_bridge_processes_a_stream_until_eof_without_logging_to_stdout():
    from personal_brain_bridge.stdio import run_stdio_stream

    source = io.StringIO(
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25"}}\n'
        '{"jsonrpc":"2.0","id":2,"method":"unknown"}\n'
    )
    output = io.StringIO()
    assert run_stdio_stream(source, output, authorized_client_id="local") == 2
    lines = output.getvalue().splitlines()
    assert len(lines) == 2
    assert '"id": 1' in lines[0]
    assert '"id": 2' in lines[1]


def test_worker_loop_polls_until_stop_and_commits_each_iteration():
    from personal_brain_worker.runtime import WorkerLoop

    calls: list[str] = []
    stop_values = iter((False, False, True))
    loop = WorkerLoop(poll=lambda: calls.append("poll"), wait=lambda _: None)
    loop.run(stop_requested=lambda: next(stop_values))
    assert calls == ["poll", "poll"]


def test_durable_worker_claims_and_dead_letters_unknown_jobs():
    from personal_brain_worker.runtime import DurableJobPoller

    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    jobs = sa.Table(
        "jobs", metadata,
        sa.Column("id", sa.String, primary_key=True), sa.Column("owner_id", sa.String, nullable=False),
        sa.Column("job_type", sa.String, nullable=False), sa.Column("payload_ref", sa.String, nullable=False),
        sa.Column("state", sa.String, nullable=False), sa.Column("priority", sa.Integer, nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False), sa.Column("max_attempts", sa.Integer, nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_owner", sa.String), sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("claim_token", sa.Integer, nullable=False), sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)), sa.Column("error_code", sa.String),
        sa.Column("error_summary", sa.String), sa.Column("result_refs", sa.JSON),
    )
    metadata.create_all(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    with factory.begin() as session:
        session.execute(jobs.insert().values(
            id="j1", owner_id="o1", job_type="unknown", payload_ref="p1", state="queued",
            priority=0, attempts=0, max_attempts=5, available_at=datetime.now(timezone.utc), claim_token=0,
        ))
    assert DurableJobPoller(factory, jobs, worker_id="w1", handlers={}).poll() == 1
    with factory() as session:
        assert session.scalar(sa.select(jobs.c.state).where(jobs.c.id == "j1")) == "dead_letter"


def test_worker_rechecks_authority_before_commit_and_reports_progress(tmp_path):
    from personal_brain_worker.runtime import DurableJobPoller, JobExecutionError

    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'jobs.sqlite').as_posix()}")
    metadata = sa.MetaData()
    jobs = sa.Table(
        "jobs", metadata,
        sa.Column("id", sa.String, primary_key=True), sa.Column("owner_id", sa.String, nullable=False),
        sa.Column("job_type", sa.String, nullable=False), sa.Column("payload_ref", sa.String, nullable=False),
        sa.Column("state", sa.String, nullable=False), sa.Column("priority", sa.Integer, nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False), sa.Column("max_attempts", sa.Integer, nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_owner", sa.String), sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("claim_token", sa.Integer, nullable=False), sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)), sa.Column("error_code", sa.String),
        sa.Column("error_summary", sa.String), sa.Column("result_refs", sa.JSON),
    )
    metadata.create_all(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    with factory.begin() as session:
        session.execute(jobs.insert().values(
            id="j2", owner_id="o1", job_type="asset", payload_ref="asset:1", state="queued",
            priority=0, attempts=0, max_attempts=5, available_at=datetime.now(timezone.utc), claim_token=0,
        ))
    phases = []

    def recheck(_job, phase):
        phases.append(phase)
        if phase == "before_commit":
            raise JobExecutionError("PERMISSION_DENIED", retryable=False)

    def handler(_job, context):
        assert context.progress(50, "parsed")
        return {"result": "must-not-commit"}

    poller = DurableJobPoller(factory, jobs, worker_id="w1", handlers={"asset": handler}, recheck=recheck)
    assert poller.poll() == 1
    with factory() as session:
        row = session.execute(sa.select(jobs)).mappings().one()
        assert row["state"] == "dead_letter" and row["error_code"] == "PERMISSION_DENIED"
        assert row["result_refs"] == {"progress": 50, "summary": "parsed"}
    assert phases == ["before_execute", "before_commit"]
    engine.dispose()


def test_production_worker_registry_covers_required_durable_work_categories(tmp_path):
    from personal_brain_infra.storage.local import LocalStorage
    from personal_brain_worker.job_handlers import build_job_handlers

    handlers = build_job_handlers(lambda: None, {}, LocalStorage(tmp_path / "assets"))
    assert {
        "extract_raw_input", "index_raw_input", "index_todo", "index_self_claim",
        "bootstrap_project", "refresh_project_context", "parse_asset", "reprocess_asset",
        "rebuild_index", "reconcile_deletion", "health_check", "dispatch_notification",
        "retention_maintenance", "notify_review",
    } <= set(handlers)
