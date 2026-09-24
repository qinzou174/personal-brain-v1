"""Red-first transaction, replay, and lease-fencing properties (FR-011/083/084)."""

from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest
from hypothesis import given, settings, strategies as st
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker


@given(crash_after=st.integers(min_value=0, max_value=3))
@settings(max_examples=8, deadline=None)
def test_crash_never_commits_only_some_canonical_side_effects(crash_after):
    from personal_brain_infra.persistence.unit_of_work import UnitOfWork

    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    tables = [
        Table(name, metadata, Column("id", String(36), primary_key=True), Column("version", Integer, nullable=False))
        for name in ("canonical", "idempotency", "jobs", "audit")
    ]
    metadata.create_all(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    request_id = str(uuid4())
    with pytest.raises(RuntimeError, match="injected crash"):
        with UnitOfWork(factory) as uow:
            for step, table in enumerate(tables):
                uow.session.execute(table.insert().values(id=request_id, version=1))
                if step == crash_after:
                    raise RuntimeError("injected crash")
            uow.commit()
    with factory() as session:
        assert all(session.scalar(select(func.count()).select_from(table)) == 0 for table in tables)
    engine.dispose()


@given(payload=st.binary(min_size=0, max_size=128), other=st.binary(min_size=0, max_size=128))
@settings(max_examples=30)
def test_idempotency_replay_or_conflict_is_deterministic(payload, other):
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_infra.persistence.idempotency import resolve_replay

    first_digest = hashlib.sha256(payload).hexdigest()
    next_digest = hashlib.sha256(other).hexdigest()
    if payload == other:
        assert resolve_replay(first_digest, next_digest, existing_outcome={"record_id": "same-id"}) == {
            "record_id": "same-id"
        }
    else:
        with pytest.raises(BrainError) as caught:
            resolve_replay(first_digest, next_digest, existing_outcome={"record_id": "same-id"})
        assert caught.value.code == "IDEMPOTENCY_CONFLICT"


@given(old_token=st.integers(min_value=1, max_value=10_000), advance=st.integers(min_value=1, max_value=100))
@settings(max_examples=30)
def test_reclaimed_job_rejects_old_worker_completion(old_token, advance):
    from personal_brain_infra.jobs.store import may_commit_result

    assert not may_commit_result(
        state="leased", submitted_claim_token=old_token, current_claim_token=old_token + advance
    )
    assert may_commit_result(
        state="leased", submitted_claim_token=old_token + advance, current_claim_token=old_token + advance
    )
    assert not may_commit_result(
        state="dead_letter", submitted_claim_token=old_token + advance, current_claim_token=old_token + advance
    )
