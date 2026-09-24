"""Provider gateway privacy boundary (T038, FR-004/006/072/084/086, ER-12)."""

import pytest


def test_provider_disabled_by_default_and_bounded_calls():
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_infra.models.gateway import ModelGateway

    gateway = ModelGateway(provider=None)
    with pytest.raises(BrainError) as caught:
        gateway.generate({}, {}, max_calls=2)
    assert caught.value.code == "TOOL_DENIED"


def test_model_card_declares_identity_dimensions_and_budget():
    from personal_brain_infra.models.gateway import ModelCard

    card = ModelCard(
        name="fixed-model", version="2026-09", dimensions=768, tokenizer="zh-bpe",
        sensitivity="private", max_input_tokens=4096,
    )
    assert card.name == "fixed-model"
    assert card.max_input_tokens > 0


def test_provider_enforces_call_context_sensitivity_and_secret_budgets():
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_infra.models.gateway import ModelCard, ModelGateway, ProviderCallBudget

    calls = []
    card = ModelCard(
        name="fixed", version="1", dimensions=768, tokenizer="zh-bpe",
        sensitivity="private", max_input_tokens=4096, provider_id="provider-a",
        max_context_bytes=1024, allowed_context_keys=("sources",),
    )
    gateway = ModelGateway(provider=lambda payload: calls.append(payload) or {"ok": True}, card=card)
    budget = ProviderCallBudget(max_calls=1)
    assert gateway.execute({"prompt": "摘要"}, {"sources": ["s1"]}, sensitivity="private", budget=budget) == {"ok": True}
    assert calls[0]["model_version"] == "1"
    with pytest.raises(BrainError) as caught:
        gateway.execute({"prompt": "again"}, {"sources": []}, sensitivity="private", budget=budget)
    assert caught.value.code == "VALIDATION_FAILED"
    with pytest.raises(BrainError) as caught:
        gateway.execute({"prompt": "token=abcdefghijklmnopqrstuvwxyz"}, {"sources": []},
                        sensitivity="private", budget=ProviderCallBudget())
    assert caught.value.code == "SECRET_REJECTED"


def test_provider_timeout_is_value_free():
    import time
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_infra.models.gateway import ModelCard, ModelGateway, ProviderCallBudget

    card = ModelCard(name="fixed", version="1", dimensions=1, tokenizer="x",
                     sensitivity="normal", max_input_tokens=10)
    gateway = ModelGateway(provider=lambda _payload: time.sleep(1.2), card=card, timeout_seconds=1)
    with pytest.raises(BrainError) as caught:
        gateway.execute({}, {}, sensitivity="normal", budget=ProviderCallBudget())
    assert caught.value.code == "BRAIN_UNAVAILABLE"
    assert "payload" not in str(caught.value).lower()


def test_worker_provider_derive_fails_closed_without_gateway():
    from datetime import datetime, timezone
    from uuid import uuid4

    import sqlalchemy as sa
    from sqlalchemy.orm import Session, sessionmaker

    from personal_brain_worker.job_handlers import build_job_handlers

    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    sa.Table(
        "derived_contents", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String, nullable=False), sa.Column("sensitivity", sa.String, nullable=False),
    )
    metadata.create_all(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    owner_id, derivation_id = uuid4(), uuid4()
    with factory.begin() as session:
        session.execute(metadata.tables["derived_contents"].insert().values(
            id=derivation_id, owner_id=owner_id, kind="summary", sensitivity="private",
        ))
    handlers = build_job_handlers(factory, metadata.tables, storage=None, gateway=None)
    from personal_brain_worker.runtime import JobExecutionError

    class FakeContext:
        def progress(self, percent, note=None):
            return True

    job = {"payload_ref": f"derivation:{derivation_id}", "owner_id": owner_id}
    with pytest.raises(JobExecutionError) as caught:
        handlers["provider_derive"](job, FakeContext())
    assert caught.value.code == "TOOL_DENIED"
    engine.dispose()


def test_worker_provider_derive_enforces_bounded_calls_and_timeout():
    import time
    from datetime import datetime, timezone
    from uuid import uuid4

    import sqlalchemy as sa
    from sqlalchemy.orm import Session, sessionmaker

    from personal_brain_infra.models.gateway import ModelCard, ModelGateway
    from personal_brain_worker.job_handlers import build_job_handlers
    from personal_brain_worker.runtime import JobExecutionError

    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    sa.Table(
        "derived_contents", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String, nullable=False), sa.Column("sensitivity", sa.String, nullable=False),
    )
    metadata.create_all(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    owner_id, derivation_id = uuid4(), uuid4()
    with factory.begin() as session:
        session.execute(metadata.tables["derived_contents"].insert().values(
            id=derivation_id, owner_id=owner_id, kind="summary", sensitivity="private",
        ))
    calls: list[list] = []
    card = ModelCard(name="fixed", version="1", dimensions=1, tokenizer="x",
                     sensitivity="private", max_input_tokens=10, allowed_context_keys=("kind",))
    gateway = ModelGateway(
        provider=lambda payload: calls.append(payload) or {"ok": True}, card=card, max_calls=1,
        timeout_seconds=1,
    )
    handlers = build_job_handlers(factory, metadata.tables, storage=None, gateway=gateway)

    class FakeContext:
        def progress(self, percent, note=None):
            return True

    job = {"payload_ref": f"derivation:{derivation_id}", "owner_id": owner_id}
    # A bounded provider call succeeds exactly once inside the worker pipeline.
    result = handlers["provider_derive"](job, FakeContext())
    assert result["derivation_id"] == str(derivation_id)
    assert len(calls) == 1
    # A provider timeout surfaces as a retryable BRAIN_UNAVAILABLE job outcome.
    clock_gateway = ModelGateway(
        provider=lambda payload: time.sleep(1.2), card=card, max_calls=1, timeout_seconds=1,
    )
    timeout_handlers = build_job_handlers(factory, metadata.tables, storage=None, gateway=clock_gateway)
    with pytest.raises(JobExecutionError) as caught:
        timeout_handlers["provider_derive"](job, FakeContext())
    assert caught.value.code == "BRAIN_UNAVAILABLE" and caught.value.retryable is True
    engine.dispose()
