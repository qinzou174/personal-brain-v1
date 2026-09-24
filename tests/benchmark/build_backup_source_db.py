"""Build a migratable, minimally populated backup-source database for T183.

Runs the physical 0001..0011 chain into a public-schema database (the same
shape production keeps) and inserts a few canonical rows so the encrypted
backup set contains real authoritative content rather than an empty schema.
"""

from __future__ import annotations

import importlib
import os
from datetime import datetime, timezone
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


def main() -> int:
    dsn = os.environ["BRAIN_TEST_POSTGRES_DSN"]
    if not (make_url(dsn).database or "").endswith("_test"):
        raise RuntimeError("backup source database name must end with _test")
    engine = create_engine(dsn)
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        operations = Operations(MigrationContext.configure(connection))
        for revision in EXPECTED_ORDER:
            module = importlib.import_module(f"migrations.versions.{revision}")
            module.op = operations
            module.upgrade()
    metadata = MetaData()
    metadata.reflect(bind=engine)
    tables = metadata.tables
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    owner_id, client_id = uuid4(), uuid4()
    with factory.begin() as session:
        session.execute(tables["owners"].insert().values(id=owner_id))
        session.execute(tables["clients"].insert().values(
            id=client_id, owner_id=owner_id, display_name="backup-seed client",
            client_type="seed", status="active", scopes=["finance", "knowledge"],
            allowed_tools=["finance.write", "knowledge.write"], permission_epoch=1,
        ))
        raw_id, intake_id = uuid4(), uuid4()
        session.execute(tables["intake_requests"].insert().values(
            id=intake_id, owner_id=owner_id, client_id=client_id, operation="add_expense",
            idempotency_key=uuid4(), received_at=now, content_ref=None, detected_intent="add_expense",
            declared_intent="add_expense", requested_scope="finance", security_decision="allow",
            intake_level="L1", state="completed", outcome_refs=[str(raw_id)],
            correlation_id=uuid4(), error_code=None,
        ))
        session.execute(tables["raw_inputs"].insert().values(
            id=raw_id, owner_id=owner_id, intake_request_id=intake_id, client_id=client_id,
            content_text="备份源数据：咖啡 25 元", asset_ref=None, content_hash="c" * 64,
            original_at=now, original_timezone="Asia/Shanghai", source_channel="seed",
            language="zh-CN", retention_policy="canonical", sensitivity="normal",
            information_class="explicit_user_statement", canonicality="canonical",
            source_kind="explicit_user_statement", source_id=raw_id, valid_from=now,
            valid_to=None, lifecycle_state="active", deleted_at=None,
        ))
        session.execute(tables["expenses"].insert().values(
            id=uuid4(), owner_id=owner_id, amount="25.0000", currency="CNY", category="food",
            description="咖啡", occurred_at=now, occurred_timezone="Asia/Shanghai",
            kind="expense", event_id=uuid4(), source_id=raw_id, sensitivity="normal",
            information_class="explicit_user_statement", canonicality="canonical",
            source_kind="explicit_user_statement", valid_from=now, valid_to=None,
            lifecycle_state="active", deleted_at=None,
        ))
    with factory() as session:
        print("expenses:", session.scalar(sa.select(sa.func.count()).select_from(tables["expenses"])))
        print("tables:", len(metadata.tables))
    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())