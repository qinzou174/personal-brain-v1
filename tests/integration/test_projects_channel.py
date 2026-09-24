"""D-projects 2026-09-25: the projects channel must work end to end from a client.

Historical breakage: ``project.read`` was missing from the default tool profile
(every read tool TOOL_DENIED), per-project scopes were never granted on create
(every write SCOPE_DENIED — an orphaned project), deletion had no review grant
on the projects scope, and there was no way to enumerate projects at all.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from activation_support import build_harness, table_rows


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    h = build_harness(tmp_path_factory)
    yield h
    h.drop_schema()


def _service(harness):
    """Real provisioning + real AuthorizedToolService bound to a real credential."""
    from pathlib import Path

    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore
    from personal_brain_infra.search.repository import PostgresSearchRepository
    from personal_brain_infra.security.authority import PersistedAuthority
    from personal_brain_server.admin import provision_client
    from personal_brain_server.api.authorized_tools import AuthorizedToolService

    credential_file = Path(harness.data_root) / f"projects-client-{uuid4().hex[:8]}.credential"
    provisioned = provision_client(
        harness.factory, harness.tables, display_name=f"projects-{uuid4().hex[:8]}",
        client_type="mobile", credential_file=credential_file,
    )
    token = credential_file.read_text(encoding="utf-8").strip()
    authority = PersistedAuthority(harness.factory, harness.tables)
    service = AuthorizedToolService(
        authority,
        lambda *, owner_id, client_id: AuthoritativeStore(
            harness.factory, owner_id=owner_id, client_id=client_id,
        ),
        search_factory=lambda *, owner_id: PostgresSearchRepository(
            harness.factory, harness.tables["search_index_entries"], owner_id=owner_id,
        ),
    )
    return service, token, provisioned


def test_create_then_read_write_and_discover_own_project(harness):
    service, token, _provisioned = _service(harness)

    created = service.create_project(
        credential=token, name="通道验证", purpose="projects channel end to end",
        requested_scope="projects", idempotency_key=uuid4(),
    )
    project_id = created["project_id"]

    # Creator self-grant: the same client reads its own project back.
    recovery = service.get_project_context(credential=token, project_id=project_id)
    assert recovery["project"]["project_id"] == project_id
    assert recovery["project"]["name"] == "通道验证"

    listing = service.list_projects(credential=token)
    assert project_id in {row["project_id"] for row in listing["projects"]}

    decision = service.record_decision(
        credential=token, project_id=project_id, statement="用恢复视图而不重建",
        rationale="原始记录是唯一权威", affected_modules=["recovery"],
        idempotency_key=uuid4(),
    )
    assert decision["status"] == "accepted"
    constraint = service.record_constraint(
        credential=token, project_id=project_id, statement="不删除原始记录",
        rationale="ER 事实规则", affected_modules=["recovery"],
        idempotency_key=uuid4(),
    )
    assert constraint["status"] == "accepted"

    recovery = service.get_project_context(credential=token, project_id=project_id)
    assert [row["statement"] for row in recovery["decisions"]] == ["用恢复视图而不重建"]
    assert [row["statement"] for row in recovery["constraints"]] == ["不删除原始记录"]

    found = service.search_project(credential=token, project_id=project_id, query="恢复视图")
    assert found["authority"] in {"exact", "hybrid"}
    changes = service.get_recent_changes(credential=token, project_id=project_id)
    assert "change_events" in changes
    freshness = service.check_freshness(credential=token, project_id=project_id)
    assert freshness["fresh"] is True  # no module cards yet: nothing is stale
    # Authorization passed; with no modules registered the lookup is NOT_FOUND.
    from personal_brain_domain.common.errors import BrainError

    with pytest.raises(BrainError) as missing:
        service.get_module_context(credential=token, project_id=project_id, module_name="无")
    assert missing.value.code == "NOT_FOUND"


def test_task_lifecycle_start_checkpoint_finalize(harness):
    service, token, _provisioned = _service(harness)
    project_id = service.create_project(
        credential=token, name="任务流验证", purpose="start-checkpoint-finalize",
        requested_scope="projects", idempotency_key=uuid4(),
    )["project_id"]

    started = service.start_task(
        credential=token, project_id=project_id, goal="打通任务链", revision="r1",
        dirty_state=False, constraints=["不动原始记录"], idempotency_key=uuid4(),
    )
    task_id = started["task_id"]
    service.checkpoint_task(
        credential=token, task_id=task_id, completed_work="完成读写验证",
        next_step="收尾", problems="无", revision="r2", requested_scope=f"project:{project_id}",
        idempotency_key=uuid4(),
    )
    # Checkpoints are readable while the task is still active.
    active_view = service.get_project_context(credential=token, project_id=project_id)
    assert active_view["active_task"]["task_id"] == task_id
    assert active_view["checkpoints"][-1]["completed_work"] == "完成读写验证"
    finished = service.finalize_task(
        credential=token, task_id=task_id, outcome="completed",
        verification="恢复视图断言全部通过", remaining_work="无",
        end_revision="r2", end_dirty_state=False, changed_files=[],
        requested_scope=f"project:{project_id}", idempotency_key=uuid4(),
    )
    assert finished["status"] == "accepted"

    recovery = service.get_project_context(credential=token, project_id=project_id)
    assert recovery["active_task"] is None  # finalized: nothing active remains


def test_project_deletion_is_gated_then_executable(harness):
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_server.admin import set_review_access

    service, token, provisioned = _service(harness)
    project_id = service.create_project(
        credential=token, name="待删项目", purpose="governed deletion of a project",
        requested_scope="projects", idempotency_key=uuid4(),
    )["project_id"]

    # The default profile holds review.write only on the review scope: deleting
    # project data needs the explicit governance switch on the projects scope.
    with pytest.raises(BrainError) as denied:
        service.create_deletion_plan(
            credential=token, targets=[["project", project_id]], dependents={},
            requested_scope="projects", idempotency_key=uuid4(),
        )
    assert denied.value.code == "SCOPE_DENIED"

    set_review_access(
        harness.factory, harness.tables, client_id=provisioned["client_id"],
        scope="projects", access="write",
        confirmed_client_id=provisioned["client_id"], confirmed_scope="projects",
    )

    plan = service.create_deletion_plan(
        credential=token, targets=[["project", project_id]], dependents={},
        requested_scope="projects", idempotency_key=uuid4(),
    )
    assert plan["confirmation_required"] is True and plan["confirmation_state"] == "pending"
    item = plan["review_item_id"]

    outcome = service.resolve_review_item(
        credential=token, item_id=item, expected_version=1, decision="approved",
        idempotency_key=uuid4(),
    )
    assert outcome["decision"] == "approved"
    rows = _project_rows(harness, project_id)
    assert rows[0]["lifecycle_state"] == "deleted"
    settled = service.get_deletion_plan(credential=token, plan_id=plan["plan_id"])
    assert settled["execution_state"] == "completed"


def test_record_decision_refresh_job_indexes_the_fact(harness):
    """record_project_fact enqueues a refresh job whose payload_ref the indexer
    used to reject as unknown (latent until the channel worked)."""
    from pathlib import Path

    from personal_brain_infra.storage.local import LocalStorage
    from personal_brain_worker.job_handlers import build_job_handlers

    service, token, provisioned = _service(harness)
    project_id = service.create_project(
        credential=token, name="事实索引验证", purpose="refresh jobs must index facts",
        requested_scope="projects", idempotency_key=uuid4(),
    )["project_id"]
    decision = service.record_decision(
        credential=token, project_id=project_id, statement="以恢复视图为唯一权威",
        rationale="验收", affected_modules=[], idempotency_key=uuid4(),
    )
    ref = f"decision:{decision['decision_id']}"
    job = [row for row in table_rows(harness, "jobs", job_type="refresh_project_context",
                                     payload_ref=ref)]
    assert len(job) >= 1  # the store may enqueue one per authorized stage

    # A single poll claims at most 10 jobs; earlier tests in this module may
    # have queued more, so drain the queue until this decision's job settles.
    handlers = build_job_handlers(harness.factory, harness.tables, LocalStorage(
        Path(harness.data_root) / "fact-assets"))
    from activation_support import run_pending_jobs

    run_pending_jobs(harness, handlers)
    cards = table_rows(harness, "search_index_entries", owner_id=UUID(provisioned["owner_id"]))
    fact_cards = [row for row in cards if row["target_type"] == "decision"
                  and str(row["target_id"]) == decision["decision_id"]]
    assert len(fact_cards) == 1
    assert fact_cards[0]["authorized_scope"] == f"project:{project_id}"


def test_create_project_rejects_blank_name_and_purpose(harness):
    from personal_brain_domain.common.errors import BrainError

    service, token, _provisioned = _service(harness)
    with pytest.raises(BrainError) as blank:
        service.create_project(
            credential=token, name="   ", purpose="x", requested_scope="projects",
            idempotency_key=uuid4(),
        )
    assert blank.value.code == "VALIDATION_FAILED"
    with pytest.raises(BrainError) as blank_purpose:
        service.create_project(
            credential=token, name="x", purpose="", requested_scope="projects",
            idempotency_key=uuid4(),
        )
    assert blank_purpose.value.code == "VALIDATION_FAILED"


def test_governed_deletion_cascades_to_facts_and_seals_reads(harness):
    """Deleting a project must take its facts with it and close every read path:
    facts declared as dependents tombstone, the recovery view turns NOT_FOUND and
    discovery stops listing the project."""
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_server.admin import set_review_access

    service, token, provisioned = _service(harness)
    project_id = service.create_project(
        credential=token, name="级联删除验证", purpose="deletion must tombstone facts",
        requested_scope="projects", idempotency_key=uuid4(),
    )["project_id"]
    decision = service.record_decision(
        credential=token, project_id=project_id, statement="删除必须级联事实",
        rationale="验收", affected_modules=[], idempotency_key=uuid4(),
    )
    constraint = service.record_constraint(
        credential=token, project_id=project_id, statement="墓碑后不可再读",
        rationale="验收", affected_modules=[], idempotency_key=uuid4(),
    )

    set_review_access(
        harness.factory, harness.tables, client_id=provisioned["client_id"],
        scope="projects", access="write",
        confirmed_client_id=provisioned["client_id"], confirmed_scope="projects",
    )
    plan = service.create_deletion_plan(
        credential=token, targets=[["project", project_id]],
        dependents={project_id: [["decision", decision["decision_id"]],
                                 ["constraint", constraint["constraint_id"]]]},
        requested_scope="projects", idempotency_key=uuid4(),
    )
    service.resolve_review_item(
        credential=token, item_id=plan["review_item_id"], expected_version=1,
        decision="approved", idempotency_key=uuid4(),
    )

    assert _project_rows(harness, project_id)[0]["lifecycle_state"] == "deleted"
    for table, fact_id in (("decisions", decision["decision_id"]),
                           ("constraints", constraint["constraint_id"])):
        rows = table_rows(harness, table, id=UUID(fact_id))
        assert rows and rows[0]["lifecycle_state"] == "deleted", f"{table} kept its fact active"

    with pytest.raises(BrainError) as gone:
        service.get_project_context(credential=token, project_id=project_id)
    assert gone.value.code == "NOT_FOUND"
    listed = {row["project_id"] for row in service.list_projects(credential=token)["projects"]}
    assert project_id not in listed


def _project_rows(harness, project_id):
    import sqlalchemy as sa

    with harness.factory() as session:
        return [dict(row) for row in session.execute(sa.select(
            harness.tables["projects"],
        ).where(harness.tables["projects"].c.id == project_id)).mappings().all()]