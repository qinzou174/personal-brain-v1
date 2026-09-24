"""ASGI runtime and evidence-based health probes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

import sqlalchemy as sa
from fastapi import APIRouter, FastAPI, Response

from personal_brain_server.bootstrap.preflight import preflight_report


ReadinessProbe = Callable[[], dict[str, object]]


def build_readiness_probe(engine: sa.Engine, data_root: Path) -> ReadinessProbe:
    def probe() -> dict[str, object]:
        database = "failed"
        worker = "failed"
        storage = "failed"
        try:
            with engine.connect() as connection:
                connection.execute(sa.text("SELECT 1"))
                database = "ok"
                # A usable durable queue is the server-side worker dependency.
                inspector = sa.inspect(connection)
                worker = "ok" if "jobs" in inspector.get_table_names() else "failed"
        except sa.exc.SQLAlchemyError:
            pass
        try:
            data_root.mkdir(parents=True, exist_ok=True)
            probe_path = data_root / ".readiness"
            with probe_path.open("ab"):
                pass
            probe_path.unlink(missing_ok=True)
            storage = "ok" if os.access(data_root, os.R_OK | os.W_OK | os.X_OK) else "failed"
        except OSError:
            pass
        return preflight_report(database=database, worker=worker, storage=storage)

    return probe


def create_app(*, readiness_probe: ReadinessProbe, protocol_router: APIRouter | None = None) -> FastAPI:
    app = FastAPI(title="Personal Brain V1", docs_url=None, redoc_url=None)
    if protocol_router is not None:
        app.include_router(protocol_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/ready")
    def ready(response: Response) -> dict[str, object]:
        report = readiness_probe()
        if not report.get("ready"):
            response.status_code = 503
        return report

    return app
