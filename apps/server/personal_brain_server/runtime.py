"""ASGI runtime and evidence-based health probes."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable

import sqlalchemy as sa
from fastapi import APIRouter, FastAPI, Header, HTTPException, Response

from personal_brain_domain.operations.doctor import aggregate_health, check_components
from personal_brain_server.bootstrap.preflight import preflight_report


ReadinessProbe = Callable[[], dict[str, object]]
DoctorProbe = Callable[[], dict[str, object]]


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


def build_doctor_probe(engine: sa.Engine, data_root: Path) -> DoctorProbe:
    """Deterministic doctor checks (FR-092) exposed over HTTP.

    Reports disk, failed jobs, corrupted assets and broken relations without
    collapsing failures into HTTP availability. Missing tables are reported as
    ``not_checked`` rather than crashing, so the probe stays honest on any
    environment.
    """

    def probe() -> dict[str, object]:
        disk_free_percent = 0.0
        try:
            usage = shutil.disk_usage(data_root)
            disk_free_percent = 100.0 * usage.free / usage.total
        except OSError:
            disk_free_percent = 0.0
        failed_jobs = -1
        corrupted_assets = -1
        broken_relations = -1
        unchecked: list[str] = []
        try:
            with engine.connect() as connection:
                inspector = sa.inspect(connection)
                tables = set(inspector.get_table_names())
                checks = (
                    ("jobs", "jobs",
                     "select count(*) from jobs where state in ('failed', 'dead_letter')"),
                    ("assets", "assets",
                     "select count(*) from assets where integrity_state in "
                     "('corrupted', 'hash_mismatch', 'missing') or processing_state = 'failed'"),
                    ("relations", "relations",
                     "select count(*) from relations where subject_id is null or object_id is null"),
                )
                for component, table_name, statement in checks:
                    if table_name not in tables:
                        continue
                    try:
                        value = connection.scalar(sa.text(statement))
                    except sa.exc.SQLAlchemyError:
                        # A check that cannot run must say so instead of pretending:
                        # silently swallowed SQL errors once made this whole probe a
                        # false "healthy" for assets and relations.
                        unchecked.append(component)
                        continue
                    if component == "jobs":
                        failed_jobs = value
                    elif component == "assets":
                        corrupted_assets = value
                    else:
                        broken_relations = value
        except sa.exc.SQLAlchemyError:
            # The database itself is unreachable: report every persisted check as
            # unrun rather than failing the endpoint.
            unchecked.extend(["jobs", "assets", "relations"])
        components = {
            "disk": "degraded" if disk_free_percent <= 15 else (
                "critical" if disk_free_percent <= 5 else "healthy"),
            "jobs": ("healthy" if failed_jobs == 0 else "failed") if failed_jobs >= 0 else "not_checked",
            "assets": ("healthy" if corrupted_assets == 0 else "failed") if corrupted_assets >= 0 else "not_checked",
            "relations": ("healthy" if broken_relations == 0 else "degraded") if broken_relations >= 0 else "not_checked",
        }
        findings = check_components(
            disk_free_percent=disk_free_percent,
            assets_corrupted=("assets",) if corrupted_assets > 0 else (),
            relations_broken=broken_relations if broken_relations > 0 else 0,
            unchecked=tuple(unchecked),
        )
        return {
            **aggregate_health(components=components),
            "findings": findings,
            "metrics": {
                "disk_free_percent": round(disk_free_percent, 1),
                "failed_jobs": failed_jobs,
                "corrupted_assets": corrupted_assets,
                "broken_relations": broken_relations,
            },
        }

    return probe


def create_app(*, readiness_probe: ReadinessProbe, protocol_router: APIRouter | None = None,
               doctor_probe: DoctorProbe | None = None,
               endpoint_token: str | None = None) -> FastAPI:
    """ASGI app with optionally gated ops endpoints.

    ``endpoint_token`` (from BRAIN_ENDPOINT_TOKEN_FILE in production) guards the
    two probes that expose runtime details.  Without it — local development —
    the full body is returned; with it, anonymous callers receive only the
    one-bit aggregate and the token unlocks the full report.
    """

    def _authorized(authorization: str | None) -> bool:
        return endpoint_token is None or authorization == f"Bearer {endpoint_token}"

    app = FastAPI(title="Personal Brain V1", docs_url=None, redoc_url=None)
    if protocol_router is not None:
        app.include_router(protocol_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/doctor")
    def doctor(authorization: str | None = Header(default=None)) -> dict[str, object]:
        if doctor_probe is None:
            return {"overall": "not_checked", "components": {}, "findings": []}
        report = doctor_probe()
        if not _authorized(authorization):
            if authorization is None:
                # Anonymous: only the one-bit aggregate — no disk/jobs/asset detail.
                return {"overall": report.get("overall", "unknown")}
            raise HTTPException(status_code=401, detail="AUTH_INVALID")
        return report

    @app.get("/ready")
    def ready(response: Response, authorization: str | None = Header(default=None)) -> dict[str, object]:
        report = readiness_probe()
        ready_flag = bool(report.get("ready"))
        if not ready_flag:
            response.status_code = 503
        if not _authorized(authorization):
            if authorization is None:
                return {"ready": ready_flag}
            raise HTTPException(status_code=401, detail="AUTH_INVALID")
        return report

    return app
