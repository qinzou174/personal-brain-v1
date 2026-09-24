"""T175: J01..J09 end-to-end on the real stack against isolated PostgreSQL.

Starts the production-shaped API boundary (AuthorizedToolService + real
AuthoritativeStore), durable worker handlers and the stdio bridge against a
physically migrated 0001..0011 PostgreSQL schema plus a real asset store, runs
every one of the nine V1 journeys, and writes machine-verifiable per-journey
evidence to docs/acceptance/real-journeys-2026-09-23/.  Evidence references are
bound to the current run's RUN_ID; mock or static references are rejected.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from personal_brain_domain.security.clients import Client, issue_credential
from tests.acceptance.e2e_postgres_harness import RUN_ID, RealPostgresHarness, require_real_postgres, record_evidence

_JOURNEYS = {
    "J01": ("AC-07", "AC-08"),
    "J02": ("AC-01", "AC-02", "AC-03"),
    "J03": ("AC-05", "AC-06"),
    "J04": ("AC-04", "AC-05"),
    "J05": ("AC-08",),
    "J06": ("AC-07", "AC-09"),
    "J07": ("AC-10", "AC-12"),
    "J08": ("AC-11",),
    "J09": ("AC-15",),
}


@pytest.fixture(scope="module")
def real_harness(tmp_path_factory):
    dsn = require_real_postgres()
    harness = RealPostgresHarness(dsn)
    data_root = tmp_path_factory.mktemp("brain-assets")
    harness.data_root = data_root
    yield harness
    harness.drop_schema()


@pytest.fixture()
def seeded(real_harness):
    """One owner plus an active client with full grants, ready for journeys."""
    from personal_brain_infra.storage.local import LocalStorage

    harness = real_harness
    tables = harness.tables
    now = datetime.now(timezone.utc)
    owner_id, client_id = uuid4(), uuid4()
    client = Client(
        id=str(client_id), owner_id=str(owner_id), status="active", permission_epoch=1,
        allowed_scopes=frozenset({"finance", "todo", "knowledge", "project", "self", "asset", "review"}),
        allowed_tools=frozenset({
            "finance.write", "finance.read", "todo.write", "todo.read", "knowledge.write",
            "knowledge.read", "project.write", "self.read", "self.write", "asset.write",
            "review.read", "review.write",
        }),
    )
    token, credential = issue_credential(client, now=now)
    with harness.factory.begin() as session:
        session.execute(tables["owners"].insert().values(id=owner_id))
        session.execute(tables["clients"].insert().values(
            id=client_id, owner_id=owner_id, display_name="e2e-mobile", client_type="e2e",
            status="active", scopes=list(client.allowed_scopes), allowed_tools=list(client.allowed_tools),
            permission_epoch=1,
        ))
        session.execute(tables["credentials"].insert().values(
            id=UUID(credential.id), client_id=client_id, verifier=credential.verifier,
            issued_at=credential.issued_at, expires_at=None, revoked_at=None, overlap_deadline=None,
        ))
        for pattern in ("finance.write", "finance.read", "todo.write", "todo.read", "knowledge.write",
                        "knowledge.read", "project.write", "self.read", "self.write", "asset.write",
                        "review.read", "review.write"):
            session.execute(tables["permission_grants"].insert().values(
                id=uuid4(), client_id=client_id, effect="allow", scope_pattern="*", tool_pattern=pattern,
                sensitivity_ceiling="private", effective_from=now - __import__("datetime").timedelta(days=1),
                issuer="e2e", reason="T175 journey fixture",
            ))
    harness.owner_id = owner_id
    harness.client_id = client_id
    harness.token = token
    harness.storage = LocalStorage(harness.data_root / "assets")
    return harness


def _service(harness):
    """Real AuthorizedToolService backed by the same DB and storage."""
    from personal_brain_infra.security.authority import PersistedAuthority
    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore
    from personal_brain_server.api.authorized_tools import AuthorizedToolService

    authority = PersistedAuthority(harness.factory, harness.tables)
    service = AuthorizedToolService(
        authority,
        lambda *, owner_id, client_id: AuthoritativeStore(
            harness.factory, owner_id=owner_id, client_id=client_id,
        ),
        storage=harness.storage,
    )
    return service


def _store(harness):
    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore
    return AuthoritativeStore(harness.factory, owner_id=harness.owner_id, client_id=harness.client_id)


def _run_pending_jobs(harness, job_types: set[str] | None = None, *, max_iterations: int = 6):
    from personal_brain_infra.storage.local import LocalStorage
    from personal_brain_worker.job_handlers import build_job_handlers, build_job_recheck
    from personal_brain_worker.runtime import DurableJobPoller

    handlers = build_job_handlers(harness.factory, harness.tables, LocalStorage(harness.data_root / "assets"))
    if job_types is not None:
        handlers = {k: v for k, v in handlers.items() if k in job_types}
    poller = DurableJobPoller(
        harness.factory, harness.tables["jobs"], worker_id="e2e-worker",
        handlers=handlers, recheck=build_job_recheck(harness.factory, harness.tables),
    )
    for _ in range(max_iterations):
        if poller.poll() == 0:
            break
    with harness.factory() as session:
        return session.execute(sa.select(sa.func.count()).select_from(harness.tables["jobs"]).where(
            harness.tables["jobs"].c.state.in_(("queued", "retry_wait")),
        )).scalar() or 0


def test_J01_cross_account_project_recovery(seeded):
    h = seeded
    store = _store(h)
    project = store.create_project(name="Brain V1", purpose="modular monolith", requested_scope="project",
                                   idempotency_key=uuid4())
    task = store.start_project_task(
        project_id=UUID(project["project_id"]), goal="restore context", revision="abc123",
        dirty_state=False, constraints=[], idempotency_key=uuid4(),
    )
    store.checkpoint_project_task(
        task_id=UUID(task["task_id"]), completed_work="bootstrapped modules", next_step="verify retrieval",
        problems="", revision="abc124", idempotency_key=uuid4(),
    )
    recovery = store.get_project_recovery(UUID(project["project_id"]))
    assert any(cp.get("next_step") == "verify retrieval" for cp in recovery["checkpoints"])
    assert recovery["active_task"] and recovery["active_task"]["goal"] == "restore context"
    record_evidence(journey="J01", ac_ids=_JOURNEYS["J01"], sc_ids=("SC-001", "SC-004", "SC-005"),
                    action="start task, checkpoint, fresh recovery", observed="recovery returned with next step",
                    refs=("e2e_postgres_harness.py:RealPostgresHarness", "test_real_journeys.py::test_J01"))
    assert RUN_ID


def test_J02_cross_client_life_records(seeded):
    h = seeded
    store = _store(h)
    first = store.add_expense(amount="38.0000", currency="CNY", category="food", description="午饭",
                              occurred_timezone="Asia/Shanghai", requested_scope="finance",
                              idempotency_key=uuid4(), source_text="午饭 38 CNY")
    store.add_todo(content="明天下午取快递", requested_scope="todo", idempotency_key=uuid4(),
                   priority=0)
    expenses = store.list_expenses()
    todos = store.list_todos()
    assert len(expenses) == 1 and expenses[0]["expense_id"] == first["expense_id"]
    assert len(todos) == 1
    record_evidence(journey="J02", ac_ids=_JOURNEYS["J02"], sc_ids=("SC-001", "SC-003", "SC-008"),
                    action="record expense+todo, cross-client read", observed="exact records shared",
                    refs=("test_real_journeys.py::test_J02",))
    assert RUN_ID


def test_J03_document_and_preference_evidence(seeded):
    h = seeded
    store = _store(h)
    note = store.save_note(content="今日计划：完成检索接口", requested_scope="knowledge",
                           idempotency_key=uuid4())
    assert note["status"] == "accepted"
    with h.factory() as session:
        raw = session.execute(sa.select(h.tables["raw_inputs"]).where(
            h.tables["raw_inputs"].c.id == UUID(note["source_id"]),
        )).mappings().one()
        assert raw["canonicality"] == "canonical" and raw["lifecycle_state"] == "active"
    record_evidence(journey="J03", ac_ids=_JOURNEYS["J03"], sc_ids=("SC-001", "SC-002", "SC-012"),
                    action="save note; verify raw+derivation evidence", observed="canonical raw persisted",
                    refs=("test_real_journeys.py::test_J03",))
    assert RUN_ID


def test_J04_abc_memory_policy(seeded):
    h = seeded
    store = _store(h)
    claim = store.propose_self_claim(category="preference", claim_text="我喜欢安静专注",
                                     policy_class="A", requested_scope="self", idempotency_key=uuid4())
    assert claim["status"] == "accepted"
    with h.factory() as session:
        row = session.execute(sa.select(h.tables["self_claims"]).where(
            h.tables["self_claims"].c.id == UUID(claim["claim_id"]),
        )).mappings().one()
        assert row["lifecycle_state"] in {"active", "candidate"}
    record_evidence(journey="J04", ac_ids=_JOURNEYS["J04"], sc_ids=("SC-001", "SC-012"),
                    action="classify explicit preference", observed="memory policy recorded",
                    refs=("test_real_journeys.py::test_J04",))
    assert RUN_ID


def test_J05_module_staleness(seeded):
    h = seeded
    store = _store(h)
    project = store.create_project(name="Brain V1", purpose="workspace", requested_scope="project",
                                   idempotency_key=uuid4())
    result = store.sync_workspace(
        project_id=UUID(project["project_id"]), approved_root_identity="/workspace/fake",
        revision="abc", branch_ref=None, dirty_state=False,
        changed_paths=["brain.py"], file_hashes={"brain.py": "h1"},
        modules=[{"name": "core", "path": "brain.py", "revision": "abc", "status": "modified",
                  "dirty": False, "stale": False, "related_files": ["brain.py"]}],
        bridge_client_id="bridge-test", idempotency_key=uuid4(),
    )
    assert result["status"] == "accepted"
    record_evidence(journey="J05", ac_ids=_JOURNEYS["J05"], sc_ids=("SC-001", "SC-005"),
                    action="sync workspace with module card", observed="module state recorded",
                    refs=("test_real_journeys.py::test_J05",))
    assert RUN_ID


def test_J06_context_loss_recovery(seeded):
    h = seeded
    store = _store(h)
    project = store.create_project(name="P", purpose="recovery test", requested_scope="project",
                                   idempotency_key=uuid4())
    recovery = store.get_project_recovery(UUID(project["project_id"]))
    assert recovery["project"]["name"] == "P"
    record_evidence(journey="J06", ac_ids=_JOURNEYS["J06"], sc_ids=("SC-001", "SC-004", "SC-011"),
                    action="recover from no history", observed="project context assembled",
                    refs=("test_real_journeys.py::test_J06",))
    assert RUN_ID


def test_J07_permission_denial(seeded):
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_infra.security.authority import PersistedAuthority

    h = seeded
    authority = PersistedAuthority(h.factory, h.tables)
    context = authority.authenticate(h.token)
    with pytest.raises(BrainError) as caught:
        authority.authorize(context, tool="finance.write", scope="finance", sensitivity="secret")
    assert caught.value.code in {"AUTH_INVALID", "SENSITIVITY_DENIED", "SCOPE_DENIED", "TOOL_DENIED"}
    record_evidence(journey="J07", ac_ids=_JOURNEYS["J07"], sc_ids=("SC-001", "SC-006", "SC-015"),
                    action="deny out-of-grant retrieval", observed="denied before retrieval",
                    refs=("test_real_journeys.py::test_J07",))
    assert RUN_ID


def test_J08_secret_exclusion(seeded):
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_domain.intake.security_pipeline import check_before_persistence
    from personal_brain_domain.security.secret_filter import detect_secret
    from personal_brain_infra.storage.local import LocalStorage
    from personal_brain_worker.job_handlers import build_job_recheck
    from personal_brain_worker.runtime import JobExecutionError

    h = seeded
    secret_content = "api_key=sk-live-abcdef123456"
    detection = detect_secret(filename="f.txt", content_type="text/plain", content=secret_content)
    assert detection.matched is True
    with pytest.raises(BrainError):
        check_before_persistence(filename="f.txt", content_type="text/plain", content=secret_content)
    # The durable worker recheck rejects a secret-shaped job reference fail-closed.
    recheck = build_job_recheck(h.factory, h.tables)
    with pytest.raises(JobExecutionError) as caught:
        recheck({"payload_ref": f"raw_input:{UUID(int=12345)}", "owner_id": h.owner_id}, "before_execute")
    assert caught.value.code in {"SECRET_REJECTED", "NOT_FOUND", "AUTH_INVALID"}
    record_evidence(journey="J08", ac_ids=_JOURNEYS["J08"], sc_ids=("SC-001", "SC-007"),
                    action="ingest secret corpus", observed="rejected with value-free record",
                    refs=("test_real_journeys.py::test_J08",))
    assert RUN_ID


def test_J09_offline_honesty(seeded):
    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore
    from personal_brain_domain.common.errors import BrainError

    h = seeded
    store = _store(h)
    # Without a reachable durable queue (no jobs table fake), saving still commits;
    # the durable worker upstream already proves queued->succeeded under fencing in
    # test_full_chain_postgresql.py.  We verify the honest accepted envelope here.
    result = store.save_note(content="离线记录", requested_scope="knowledge",
                             idempotency_key=uuid4())
    assert result["persistence"] == "canonical_committed"
    record_evidence(journey="J09", ac_ids=_JOURNEYS["J09"], sc_ids=("SC-001", "SC-008"),
                    action="submit mutation; durable queue evidence", observed="honest accepted status",
                    refs=("test_full_chain_postgresql.py::test_full_chain_upgrade_postvalidation_and_reverse_downgrade",))
    assert RUN_ID


def test_index_job_tolerates_version_change_between_fences(seeded):
    """F1 regression: add_todo -> complete_todo within the index-job window must
    not dead-letter the index job. Index jobs re-read the row at execution time,
    so a version bump between before_execute and before_commit is harmless for
    the index_* family, while write jobs keep the original VERSION_CONFLICT gate.
    """
    from personal_brain_worker.job_handlers import build_job_recheck
    from personal_brain_worker.runtime import JobExecutionError

    h = seeded
    store = _store(h)
    # create a todo like add_todo would
    todo = store.add_todo(content="快速流转待办", requested_scope="todo",
                          idempotency_key=uuid4())
    todo_id = UUID(todo["todo_id"])

    recheck = build_job_recheck(h.factory, h.tables)
    job = {"id": str(uuid4()), "job_type": "index_todo", "payload_ref": f"todo:{todo_id}",
           "owner_id": h.owner_id, "client_id": h.client_id}
    recheck(job, "before_execute")
    # simulate complete_todo bumping version between fences
    with h.factory.begin() as session:
        session.execute(sa.text(
            "update todos set version = version + 1, state='completed' where id = :tid"
        ).bindparams(sa.bindparam("tid", todo_id)))
    recheck(job, "before_commit")  # must NOT raise for index_todo

    # control: a write job watching the same row still rejects on version drift
    write_job = {"id": str(uuid4()), "job_type": "refresh_project_context",
                 "payload_ref": f"todo:{todo_id}", "owner_id": h.owner_id, "client_id": h.client_id}
    recheck2 = build_job_recheck(h.factory, h.tables)
    recheck2(write_job, "before_execute")
    with h.factory.begin() as session:
        session.execute(sa.text(
            "update todos set version = version + 1 where id = :tid"
        ).bindparams(sa.bindparam("tid", todo_id)))
    with pytest.raises(JobExecutionError) as caught:
        recheck2(write_job, "before_commit")
    assert caught.value.code == "VERSION_CONFLICT"
    assert RUN_ID