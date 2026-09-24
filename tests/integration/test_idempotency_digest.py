"""Contract: the idempotency digest covers outcome-changing parameters.

A replayed key with different parameters must surface ``IDEMPOTENCY_CONFLICT``
instead of silently returning the old record (the changed priority / revision /
policy class used to be dropped without any signal).
"""

from __future__ import annotations

import uuid

import pytest

from personal_brain_domain.common.errors import BrainError


def test_add_todo_conflicting_priority_is_not_silently_replayed(tmp_path):
    import sqlalchemy as sa
    from sqlalchemy.orm import Session, sessionmaker

    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore

    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    from tests.integration.test_authoritative_store import _schema, _seed  # reuse fixtures

    metadata = _schema(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    owner_id, client_id = _seed(factory, metadata)
    store = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)
    key = uuid.uuid4()
    first = store.add_todo(content="买菜", requested_scope="todo", idempotency_key=key, priority=1)
    with pytest.raises(BrainError) as conflict:
        store.add_todo(content="买菜", requested_scope="todo", idempotency_key=key, priority=9)
    assert conflict.value.code == "IDEMPOTENCY_CONFLICT"
    replay = store.add_todo(content="买菜", requested_scope="todo", idempotency_key=key, priority=1)
    assert replay["todo_id"] == first["todo_id"]


def test_propose_self_claim_conflicting_policy_class_conflicts(tmp_path):
    import sqlalchemy as sa
    from sqlalchemy.orm import Session, sessionmaker

    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore

    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    from tests.integration.test_authoritative_store import _schema, _seed

    metadata = _schema(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    owner_id, client_id = _seed(factory, metadata)
    store = AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)
    key = uuid.uuid4()
    store.propose_self_claim(category="value", claim_text="证据优先", policy_class="A",
                             requested_scope="self", idempotency_key=key)
    with pytest.raises(BrainError) as conflict:
        store.propose_self_claim(category="value", claim_text="证据优先", policy_class="B",
                                 requested_scope="self", idempotency_key=key)
    assert conflict.value.code == "IDEMPOTENCY_CONFLICT"