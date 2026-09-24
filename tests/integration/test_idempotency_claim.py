"""Durable request key, conflict, completion and deletion lifecycle (T025)."""

from __future__ import annotations

import pytest
from sqlalchemy import Column, JSON, MetaData, String, Table, UniqueConstraint, create_engine, select
from sqlalchemy.orm import Session

from personal_brain_domain.common.errors import BrainError


def test_claim_replay_conflict_and_tombstone():
    from personal_brain_infra.persistence.idempotency import claim_request, complete_claim, tombstone_claim
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    records = Table(
        "idempotency_records", metadata,
        Column("id", String, primary_key=True), Column("owner_id", String, nullable=False),
        Column("client_id", String, nullable=False), Column("operation", String, nullable=False),
        Column("idempotency_key", String, nullable=False), Column("payload_digest", String),
        Column("outcome", JSON), Column("status", String, nullable=False),
        UniqueConstraint("client_id", "operation", "idempotency_key"),
    )
    metadata.create_all(engine)
    with Session(engine) as session:
        first = claim_request(session, records, owner_id="o", client_id="c", operation="save",
                              idempotency_key="k", payload_digest="digest-a")
        assert first.state == "created"
        complete_claim(session, records, claim_id=first.id, outcome={"record_id": "one"})
        session.commit()
    with Session(engine) as session:
        replay = claim_request(session, records, owner_id="o", client_id="c", operation="save",
                               idempotency_key="k", payload_digest="digest-a")
        assert replay.state == "replay" and replay.outcome == {"record_id": "one"}
        with pytest.raises(BrainError) as caught:
            claim_request(session, records, owner_id="o", client_id="c", operation="save",
                          idempotency_key="k", payload_digest="digest-b")
        assert caught.value.code == "IDEMPOTENCY_CONFLICT"
        tombstone_claim(session, records, claim_id=first.id)
        session.commit()
    with Session(engine) as session:
        late = claim_request(session, records, owner_id="o", client_id="c", operation="save",
                             idempotency_key="k", payload_digest="digest-a")
        assert late.state == "deleted"
        row = session.execute(select(records)).mappings().one()
        assert row["payload_digest"] is None and row["outcome"] is None
    engine.dispose()
