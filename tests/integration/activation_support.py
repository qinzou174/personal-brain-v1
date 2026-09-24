"""Shared helpers for the backend-activation integration suites (real PostgreSQL).

All suites run against the physically migrated 0001..0012 schema in an isolated
``*_test`` database (``tests.acceptance.e2e_postgres_harness``), a real
LocalStorage asset store and the real worker registry.  Provider doubles are
deterministic in-process functions behind the real bounded ModelGateway, so the
gateway still enforces call budgets, sensitivity and secret rejection.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import sqlalchemy as sa

from personal_brain_infra.models.gateway import ModelCard, ModelGateway
from personal_brain_infra.storage.local import LocalStorage

LOCAL_TZ = ZoneInfo("Asia/Shanghai")

# Mirrors the production worker card in apps/worker/personal_brain_worker/__main__.py
CONTEXT_KEYS = ("sources", "payload_ref", "target_type", "kind")


def _load_harness_module():
    """Import the acceptance harness no matter how pytest set up ``sys.path``.

    ``tests/integration`` is not a package, so pytest's prepend import mode puts
    that directory first while collecting these modules; the project root (needed
    for ``tests.*`` imports) is added afterwards.
    """
    try:
        from tests.acceptance import e2e_postgres_harness
    except ModuleNotFoundError:
        import pathlib
        import sys

        root = str(pathlib.Path(__file__).resolve().parents[2])
        if root not in sys.path:
            sys.path.insert(0, root)
        from tests.acceptance import e2e_postgres_harness
    return e2e_postgres_harness


def build_harness(tmp_path_factory):
    harness_module = _load_harness_module()
    harness = harness_module.RealPostgresHarness(harness_module.require_real_postgres())
    harness.data_root = tmp_path_factory.mktemp("activation-assets")
    harness.storage = LocalStorage(harness.data_root / "assets")
    return harness


def local_at(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    """Aware UTC instant corresponding to a local (Asia/Shanghai) wall time."""
    return datetime(year, month, day, hour, minute, tzinfo=LOCAL_TZ).astimezone(timezone.utc)


def seed_owner(harness: RealPostgresHarness) -> tuple[UUID, UUID]:
    """Insert one owner plus an active client (no grants needed by the worker)."""
    owner_id, client_id = uuid4(), uuid4()
    with harness.factory.begin() as session:
        session.execute(harness.tables["owners"].insert().values(id=owner_id))
        session.execute(harness.tables["clients"].insert().values(
            id=client_id, owner_id=owner_id, display_name="activation-client",
            client_type="test", status="active", scopes=["knowledge", "self", "finance", "todo"],
            allowed_tools=["knowledge.write", "self.write"], permission_epoch=1,
        ))
    return owner_id, client_id


def insert_raw_input(
    harness: RealPostgresHarness, owner_id: UUID, client_id: UUID, *,
    text: str, scope: str = "knowledge", original_at: datetime | None = None,
    channel: str = "api",
) -> UUID:
    """One canonical intake+raw pair exactly as the production store would write it."""
    intake_id, raw_id = uuid4(), uuid4()
    now = original_at or datetime.now(timezone.utc)
    with harness.factory.begin() as session:
        session.execute(harness.tables["intake_requests"].insert().values(
            id=intake_id, owner_id=owner_id, client_id=client_id, operation="save_note",
            idempotency_key=uuid4(), received_at=now, content_ref=None,
            detected_intent="save_note", declared_intent="save_note", requested_scope=scope,
            security_decision="allow", intake_level="L1", state="completed",
            outcome_refs=[str(raw_id)], correlation_id=uuid4(), error_code=None,
        ))
        session.execute(harness.tables["raw_inputs"].insert().values(
            id=raw_id, owner_id=owner_id, intake_request_id=intake_id, client_id=client_id,
            content_text=text, asset_ref=None,
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            original_at=now, original_timezone="UTC", source_channel=channel, language="zh-CN",
            retention_policy="canonical", sensitivity="normal",
            information_class="explicit_user_statement", canonicality="canonical",
            source_kind="explicit_user_statement", source_id=raw_id,
            valid_from=now, valid_to=None, lifecycle_state="active", deleted_at=None,
        ))
    return raw_id


def queue_job(
    harness: RealPostgresHarness, owner_id: UUID, *, job_type: str, payload_ref: str,
    client_id: UUID | None = None, started_at: datetime | None = None,
    state: str = "queued", idempotency_key: UUID | None = None,
) -> UUID:
    job_id = uuid4()
    now = datetime.now(timezone.utc)
    with harness.factory.begin() as session:
        session.execute(harness.tables["jobs"].insert().values(
            id=job_id, owner_id=owner_id, client_id=client_id, job_type=job_type,
            payload_ref=payload_ref, idempotency_key=idempotency_key, state=state,
            priority=0, attempts=0, max_attempts=5, available_at=now, claim_token=0,
            started_at=started_at,
        ))
    return job_id


def insert_self_claim(
    harness: RealPostgresHarness, owner_id: UUID, *, claim: str, source_id: UUID,
    category: str = "preference", policy_class: str = "B",
    lifecycle_state: str = "candidate", establishment: str = "candidate",
    context: str = "api:knowledge", created_at: datetime | None = None,
    correction_events: list[dict[str, Any]] | None = None,
) -> UUID:
    claim_id = uuid4()
    now = created_at or datetime.now(timezone.utc)
    with harness.factory.begin() as session:
        session.execute(harness.tables["self_claims"].insert().values(
            id=claim_id, owner_id=owner_id, category=category, claim=claim,
            policy_class=policy_class, lifecycle_state=lifecycle_state,
            establishment=establishment, review="none", correction_events=correction_events or [],
            confidence_inputs={}, evidence_summary=[], valid_from=now, valid_to=None,
            context=context, exceptions=[], confirmation_identity=None, confirmation_time=None,
            source_id=source_id, created_at=now, updated_at=now,
        ))
    return claim_id


def insert_evidence(
    harness: RealPostgresHarness, owner_id: UUID, *, claim_id: UUID, source_id: UUID,
    observed_at: datetime, stance: str = "supports", context: str = "api:knowledge",
) -> UUID:
    evidence_id = uuid4()
    with harness.factory.begin() as session:
        session.execute(harness.tables["evidence"].insert().values(
            id=evidence_id, owner_id=owner_id, target_type="self_claim", target_id=claim_id,
            source_type="raw_input", source_id=source_id, stance=stance,
            source_trust="explicit_user_statement", observed_at=observed_at,
            context=context, contribution=None, lifecycle_state="active",
        ))
    return evidence_id


class FakeProvider:
    """Deterministic provider double; the real gateway still bounds the call."""

    def __init__(self, responder: Callable[[dict[str, Any]], str]) -> None:
        self._responder = responder
        self.calls: list[dict[str, Any]] = []

    def __call__(self, payload: dict[str, Any], *, timeout_seconds: int = 60) -> dict[str, Any]:
        self.calls.append(payload)
        return {"text": self._responder(payload), "model": "fake-model", "stop_reason": "end_turn",
                "usage": {}}


def constant_provider(text: str) -> FakeProvider:
    return FakeProvider(lambda _payload: text)


def gateway_for(provider: FakeProvider) -> ModelGateway:
    card = ModelCard(
        name="fake-extract-model", version="fake-v1", dimensions=0, tokenizer="fake",
        sensitivity="private", max_input_tokens=32768, provider_id="test-provider",
        allowed_context_keys=CONTEXT_KEYS,
    )
    return ModelGateway(provider=provider, card=card, timeout_seconds=30, max_calls=1)


class FakeContext:
    """Minimal job context accepted by worker handlers when called directly."""

    def __init__(self) -> None:
        self.progress_notes: list[tuple[int, str]] = []

    def progress(self, percent: int, summary: str = "") -> bool:
        self.progress_notes.append((percent, summary))
        return True


def run_pending_jobs(harness: RealPostgresHarness, handlers: dict[str, Any],
                     *, max_iterations: int = 10) -> int:
    """Claim and execute every currently queued job with the real poller/fencing."""
    from personal_brain_worker.job_handlers import build_job_recheck
    from personal_brain_worker.runtime import DurableJobPoller

    poller = DurableJobPoller(
        harness.factory, harness.tables["jobs"], worker_id="activation-test",
        handlers=handlers, recheck=build_job_recheck(harness.factory, harness.tables),
    )
    processed = 0
    for _ in range(max_iterations):
        claimed = poller.poll()
        processed += claimed
        if claimed == 0:
            break
    return processed


def job_state(harness: RealPostgresHarness, job_id: UUID) -> dict[str, Any]:
    with harness.factory() as session:
        return dict(session.execute(sa.select(harness.tables["jobs"]).where(
            harness.tables["jobs"].c.id == job_id,
        )).mappings().one())


def table_rows(harness: RealPostgresHarness, table: str, **filters: Any) -> list[dict[str, Any]]:
    with harness.factory() as session:
        statement = sa.select(harness.tables[table])
        for column, value in filters.items():
            statement = statement.where(harness.tables[table].c[column] == value)
        return [dict(row) for row in session.execute(statement).mappings().all()]


def utc_days_ago(days: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)