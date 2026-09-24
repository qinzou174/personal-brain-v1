"""Authoritative 0001..0011 physical migration chain on isolated PostgreSQL."""

from __future__ import annotations

import importlib
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import MetaData, create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

EXPECTED_ORDER = [
    "0001_authority_core", "0002_life_records", "0003_lineage_constraints",
    "0004_memory_self_model", "0005_project_brain", "0006_assets_search",
    "0007_retrieval_context", "0008_lifecycle_deletion", "0009_external_sources",
    "0010_operations", "0011_notifications", "0012_search_read_grants",
]


def test_full_chain_upgrade_postvalidation_and_reverse_downgrade(tmp_path):
    dsn = os.environ.get("BRAIN_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("BRAIN_TEST_POSTGRES_DSN unavailable; requires isolated PostgreSQL")
    if not (make_url(dsn).database or "").endswith("_test"):
        pytest.fail("migration test database name must end with _test")

    schema = "brain_migration_test_" + uuid4().hex
    engine = create_engine(dsn)
    modules = [importlib.import_module(f"migrations.versions.{revision}") for revision in EXPECTED_ORDER]
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text("SELECT set_config('search_path', :schema, true)"), {"schema": schema})
            operations = Operations(MigrationContext.configure(connection))
            expected_tables: set[str] = set()
            for migration in modules:
                assert connection.scalar(text(migration.PREFLIGHT_SQL)) is True
                migration.op = operations
                migration.upgrade()
                expected_tables.update(migration.CREATED_TABLES)
                postvalidation = connection.scalar(text(migration.POST_VALIDATION_SQL))
                if isinstance(postvalidation, bool):
                    assert postvalidation is True
                else:
                    assert postvalidation == len(migration.CREATED_TABLES)

            inspector = inspect(connection)
            actual_tables = set(inspector.get_table_names(schema=schema))
            assert expected_tables <= actual_tables
            assert len(actual_tables) == len(expected_tables)
            index_names = {
                index["name"]
                for table in actual_tables
                for index in inspector.get_indexes(table, schema=schema)
            }
            assert {"ix_jobs_claimable", "ix_expenses_owner_period", "ix_self_claims_category"} <= index_names
            assert {"ix_search_index_fts", "ix_search_index_vector_version"} <= index_names
            search_columns = {column["name"] for column in inspector.get_columns("search_index_entries", schema=schema)}
            assert {"search_document", "embedding", "vector_model_version"} <= search_columns

            # Execute the production repository against physical FTS and pgvector columns.
            from personal_brain_infra.search.repository import PostgresSearchRepository

            metadata = MetaData()
            metadata.reflect(connection, schema=schema, only=("owners", "search_index_entries"))
            owner_id, target_id = uuid4(), uuid4()
            connection.execute(metadata.tables[f"{schema}.owners"].insert().values(id=owner_id))
            factory = sessionmaker(bind=connection, class_=Session, expire_on_commit=False,
                                   join_transaction_mode="create_savepoint")
            repository = PostgresSearchRepository(
                factory, metadata.tables[f"{schema}.search_index_entries"], owner_id=owner_id,
            )
            repository.index(
                target_type="raw_input", target_id=target_id, authorized_scope="knowledge",
                sensitivity="private", canonicality="canonical", freshness="stale",
                text="今天去了京都 PersonalBrain", source_links=["source:one"],
                vector_model_version="fixture-v1", embedding=[0.1, 0.2, 0.3],
                warnings=["uncertain"],
            )
            hits = repository.search(
                query="京都", authorized_scope="knowledge", sensitivity_ceiling="private",
                query_embedding=[0.1, 0.2, 0.3], vector_model_version="fixture-v1",
            )
            assert hits[0]["target_id"] == str(target_id)
            assert hits[0]["source_links"] == ["source:one"]
            assert set(hits[0]["warnings"]) == {"uncertain", "freshness:stale"}

            # A real durable worker job indexes canonical data and settles under fencing.
            from personal_brain_infra.storage.local import LocalStorage
            from personal_brain_worker.job_handlers import build_job_handlers, build_job_recheck
            from personal_brain_worker.runtime import DurableJobPoller

            all_metadata = MetaData()
            all_metadata.reflect(connection, schema=schema)
            tables = {table.name: table for table in all_metadata.tables.values()}
            client_id, intake_id, raw_id, job_id, request_key, correlation_id = (uuid4() for _ in range(6))
            now = datetime.now(timezone.utc)
            connection.execute(tables["clients"].insert().values(
                id=client_id, owner_id=owner_id, display_name="worker fixture", client_type="test",
                status="active", scopes=["knowledge"], allowed_tools=["knowledge.write"], permission_epoch=1,
            ))
            connection.execute(tables["intake_requests"].insert().values(
                id=intake_id, owner_id=owner_id, client_id=client_id, operation="save_note",
                idempotency_key=request_key, received_at=now, content_ref=None,
                detected_intent="save_note", declared_intent="save_note", requested_scope="knowledge",
                security_decision="allow", intake_level="L1", state="completed",
                outcome_refs=[str(raw_id)], correlation_id=correlation_id, error_code=None,
            ))
            connection.execute(tables["raw_inputs"].insert().values(
                id=raw_id, owner_id=owner_id, intake_request_id=intake_id, client_id=client_id,
                content_text="项目使用 PostgreSQL 持久检索", asset_ref=None, content_hash="1" * 64,
                original_at=now, original_timezone="UTC", source_channel="test", language="zh-CN",
                retention_policy="canonical", sensitivity="private", information_class="explicit_user_statement",
                canonicality="canonical", source_kind="explicit_user_statement", source_id=raw_id,
                valid_from=now, valid_to=None, lifecycle_state="active", deleted_at=None,
            ))
            connection.execute(tables["jobs"].insert().values(
                id=job_id, owner_id=owner_id, client_id=client_id, job_type="extract_raw_input",
                payload_ref=f"raw_input:{raw_id}", idempotency_key=request_key, state="queued",
                priority=0, attempts=0, max_attempts=5, available_at=now, claim_token=0,
            ))
            handlers = build_job_handlers(factory, tables, LocalStorage(tmp_path / "assets"))
            poller = DurableJobPoller(
                factory, tables["jobs"], worker_id="physical-test", handlers=handlers,
                recheck=build_job_recheck(factory, tables),
            )
            assert poller.poll() == 1
            assert connection.scalar(sa.select(tables["jobs"].c.state).where(
                tables["jobs"].c.id == job_id,
            )) == "succeeded"
            worker_hits = repository.search(
                query="持久检索", authorized_scope="knowledge", sensitivity_ceiling="private",
            )
            assert any(hit["target_id"] == str(raw_id) for hit in worker_hits)

            for migration in reversed(modules):
                migration.op = operations
                migration.downgrade()
            assert inspect(connection).get_table_names(schema=schema) == []
            connection.execute(text(f'DROP SCHEMA "{schema}"'))
    finally:
        engine.dispose()
