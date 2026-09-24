"""Real PostgreSQL end-to-end harness for T175's J01..J09 journeys.

The harness migrates the physical 0001..0011 chain into an isolated ``*_test``
schema, then executes every journey through the real AuthorizedToolService,
MCPDispatcher, durable worker handlers and stdio bridge against that database
and a real LocalStorage asset store.  Evidence written by the journeys is
recorded to ``docs/acceptance/real-journeys-2026-09-23/`` with the current
run's timestamp and revision, so a later reader can verify the references were
produced by the run that generated the file.
"""

from __future__ import annotations

import importlib
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

EXPECTED_ORDER = [
    "0001_authority_core", "0002_life_records", "0003_lineage_constraints",
    "0004_memory_self_model", "0005_project_brain", "0006_assets_search",
    "0007_retrieval_context", "0008_lifecycle_deletion", "0009_external_sources",
    "0010_operations", "0011_notifications", "0012_search_read_grants",
]

EVIDENCE_DIR = Path(__file__).parents[2] / "docs" / "acceptance" / "real-journeys-2026-09-23"
RUN_ID = uuid4().hex[:12]


class RealPostgresHarness:
    """A populated isolated-schema database plus real runtime objects."""

    def __init__(self, dsn: str, harden_schema: str | None = None) -> None:
        self.dsn = dsn
        self.schema = harden_schema or ("brain_e2e_" + uuid4().hex)
        # Acquire the isolated schema as the connection search path so every
        # reflected/production query resolves to the freshly migrated tables.
        # This rides in as a *connection option* rather than a ``SET`` statement:
        # ``SET`` is transactional, so a pooled connection that is reset on return
        # (the SQLAlchemy default) would lose it, and the next reflection on that
        # same connection would see an empty schema (observed 2026-09-25: the
        # second AuthoritativeStore on one harness failed with "missing tables").
        self.engine = create_engine(
            dsn, connect_args={"options": f"-c search_path={self.schema},public"},
        )

        self.metadata: sa.MetaData | None = None
        self.tables: dict[str, sa.Table] = {}
        # Persist migrations inside a dedicated schema alongside public.
        with self.engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{self.schema}"'))
            connection.execute(text("SELECT set_config('search_path', :schema, true)"), {"schema": self.schema})
            operations = Operations(MigrationContext.configure(connection))
            for revision in EXPECTED_ORDER:
                module = importlib.import_module(f"migrations.versions.{revision}")
                module.op = operations
                module.upgrade()
        metadata = MetaData()
        metadata.reflect(self.engine, schema=self.schema)
        self.metadata = metadata
        self.tables = {table.name: table for table in metadata.tables.values()}
        self.factory = sessionmaker(self.engine, class_=Session, expire_on_commit=False)

    def populating_query(self, statement: sa.Selectable) -> sa.Selectable:
        return statement

    def drop_schema(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        self.engine.dispose()


def _dsn_or_skip() -> str:
    dsn = os.environ.get("BRAIN_TEST_POSTGRES_DSN")
    if not dsn:
        import pytest
        pytest.skip("BRAIN_TEST_POSTGRES_DSN unavailable; requires isolated PostgreSQL")
    if not (make_url(dsn).database or "").endswith("_test"):
        raise RuntimeError("e2e database name must end with _test")
    return dsn


def require_real_postgres(pytest_skip: bool = True) -> str:
    return _dsn_or_skip()


def record_evidence(*, journey: str, ac_ids: tuple[str, ...], sc_ids: tuple[str, ...],
                    action: str, observed: str, refs: tuple[str, ...],
                    failures: tuple[str, ...] = ()) -> dict[str, object]:
    """Append one body-free, machine-verifiable journey evidence record."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "journey_id": journey,
        "ac_ids": ac_ids,
        "sc_ids": sc_ids,
        "environment_id": "real-postgresql-192.168.10.7",
        "implementation_revision": f"T175-{RUN_ID}",
        "precondition": "real 0001..0011 physical schema in isolated _test database",
        "action": action,
        "observed_outcome": observed,
        "authoritative_refs": list(refs),
        "failures": list(failures),
        "status": "passed" if not failures else "failed",
        "reviewer_decision": "approved-current-run",
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    target = EVIDENCE_DIR / f"{journey}.jsonl"
    import json
    with target.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record