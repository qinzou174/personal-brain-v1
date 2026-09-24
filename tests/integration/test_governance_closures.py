"""Governance closes its loops: verdicts land, expired plans terminate, tombstoned
projects refuse writes, and a waiting review item actually reaches the owner.

Each test pins one of the five owner-visible gaps fixed on 2026-09-25.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from activation_support import build_harness, run_pending_jobs, seed_owner, table_rows


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    h = build_harness(tmp_path_factory)
    yield h
    h.drop_schema()


def _store(harness, owner_id, client_id):
    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore

    return AuthoritativeStore(harness.factory, owner_id=owner_id, client_id=client_id)


def _handlers(harness):
    from personal_brain_infra.storage.local import LocalStorage
    from personal_brain_worker.job_handlers import build_job_handlers

    return build_job_handlers(harness.factory, harness.tables, LocalStorage(
        Path(harness.data_root) / "governance-assets"))


def test_conflict_verdict_closes_the_conflict_and_stops_regeneration(harness):
    """Approving a contradiction item must resolve the underlying conflict row —
    otherwise the daily scan regenerated the same item every single day."""
    from personal_brain_worker.evolution import make_conflict_handler

    owner_id, client_id = seed_owner(harness)
    store = _store(harness, owner_id, client_id)
    # One established "likes tea" claim and one candidate "dislikes tea" claim:
    # a polarity contradiction the scan is designed to surface.
    first = store.propose_self_claim(category="preference", claim_text="我喜欢喝茶",
                                      policy_class="A", requested_scope="self",
                                      idempotency_key=uuid4())
    second = store.propose_self_claim(category="preference", claim_text="我不喜欢喝茶",
                                      policy_class="B", requested_scope="self",
                                      idempotency_key=uuid4())
    with harness.factory.begin() as session:
        import sqlalchemy as sa

        claims = harness.tables["self_claims"]
        session.execute(claims.update().where(
            claims.c.id == UUID(first["claim_id"]),
        ).values(lifecycle_state="active", establishment="established"))
        session.execute(claims.update().where(
            claims.c.id == UUID(second["claim_id"]),
        ).values(review="none"))

    handler = make_conflict_handler(harness.factory, harness.tables)
    context = _Context()
    first_scan = handler({"owner_id": str(owner_id)}, context)
    assert first_scan["conflicts"] == 1

    item = [row for row in table_rows(harness, "review_inbox_items", owner_id=owner_id)
            if row["item_type"] == "conflict" and row["state"] == "open"][-1]
    outcome = store.resolve_review_item(
        item_id=item["id"], expected_version=1, decision="approved",
        idempotency_key=uuid4(),
    )
    assert outcome["decision"] == "approved"
    conflicts = table_rows(harness, "conflicts", owner_id=owner_id)
    assert conflicts[0]["state"] == "resolved_by_user"
    assert conflicts[0]["resolution"]["decision"] == "approved"

    # The verdict is final: the next daily scan must NOT regenerate the pair.
    second_scan = handler({"owner_id": str(owner_id)}, _Context())
    assert second_scan["conflicts"] == 0
    open_items = [row for row in table_rows(harness, "review_inbox_items", owner_id=owner_id)
                  if row["item_type"] == "conflict" and row["state"] == "open"]
    assert open_items == []


def test_expired_deletion_plan_terminates_instead_of_staying_pending(harness):
    """A confirmation past its 15-minute window is a terminal state: the item and
    its plan close, and the plan never advertises itself as pending again."""
    owner_id, client_id = seed_owner(harness)
    store = _store(harness, owner_id, client_id)
    note = store.save_note(content="过期验证", requested_scope="knowledge", idempotency_key=uuid4())
    plan = store.create_deletion_plan(
        targets=[("raw_input", UUID(note["record_id"]))], dependents={},
        requested_scope="knowledge", idempotency_key=uuid4(),
    )
    with harness.factory.begin() as session:
        import sqlalchemy as sa

        items = harness.tables["review_inbox_items"]
        session.execute(items.update().where(
            items.c.id == UUID(plan["review_item_id"]),
        ).values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))

    outcome = store.resolve_review_item(
        item_id=UUID(plan["review_item_id"]), expected_version=1, decision="approved",
        idempotency_key=uuid4(),
    )
    assert outcome["status"] == "expired"
    item = table_rows(harness, "review_inbox_items", id=UUID(plan["review_item_id"]))[0]
    assert item["state"] == "resolved"
    plan_row = table_rows(harness, "deletion_plans", id=UUID(plan["plan_id"]))[0]
    assert plan_row["confirmation_state"] == "expired"
    assert plan_row["execution_state"] == "preview"  # nothing was deleted


def test_tombstoned_project_refuses_every_write(harness):
    owner_id, client_id = seed_owner(harness)
    store = _store(harness, owner_id, client_id)
    project_id = UUID(store.create_project(
        name="写门禁验证", purpose="writes must follow the project into the grave",
        requested_scope="projects", idempotency_key=uuid4(),
    )["project_id"])
    decision = store.record_project_fact(
        kind="decision", project_id=project_id, statement="项目期间的决定",
        rationale="x", affected_modules=[], idempotency_key=uuid4(),
    )
    task_id = UUID(store.start_project_task(
        project_id=project_id, goal="任务", revision="r1", dirty_state=False,
        constraints=[], idempotency_key=uuid4(),
    )["task_id"])
    store.checkpoint_project_task(
        task_id=task_id, completed_work="进行中", next_step="x", problems="",
        revision="r2", idempotency_key=uuid4(),
    )

    from personal_brain_server.admin import set_review_access
    set_review_access(harness.factory, harness.tables, client_id=client_id,
                      scope="projects", access="write",
                      confirmed_client_id=client_id, confirmed_scope="projects")
    plan = store.create_deletion_plan(
        targets=[("project", project_id)], dependents={},
        requested_scope="projects", idempotency_key=uuid4(),
    )
    store.resolve_review_item(item_id=UUID(plan["review_item_id"]), expected_version=1,
                              decision="approved", idempotency_key=uuid4())
    plan_row = table_rows(harness, "deletion_plans", id=UUID(plan["plan_id"]))[0]
    project_row = table_rows(harness, "projects", id=project_id)[0]
    assert plan_row["execution_state"] == "completed", plan_row
    assert project_row["lifecycle_state"] == "deleted", project_row

    from personal_brain_domain.common.errors import BrainError
    with pytest.raises(BrainError) as fact_denied:
        store.record_project_fact(kind="decision", project_id=project_id,
                                  statement="删后再写", rationale="x", affected_modules=[],
                                  idempotency_key=uuid4())
    assert fact_denied.value.code == "NOT_FOUND"
    with pytest.raises(BrainError) as task_denied:
        store.start_project_task(project_id=project_id, goal="再开任务", revision="r1",
                                 dirty_state=False, constraints=[], idempotency_key=uuid4())
    assert task_denied.value.code == "NOT_FOUND"
    with pytest.raises(BrainError) as sync_denied:
        store.sync_workspace(project_id=project_id, approved_root_identity="root",
                             revision="r3", branch_ref=None, dirty_state=False,
                             changed_paths=["a"], file_hashes={"a": "h"}, modules=[],
                             bridge_client_id=client_id, idempotency_key=uuid4())
    assert sync_denied.value.code == "NOT_FOUND"
    with pytest.raises(BrainError) as checkpoint_denied:
        store.checkpoint_project_task(task_id=task_id, completed_work="删后再更",
                                      next_step="x", problems="", revision="r3",
                                      idempotency_key=uuid4())
    assert checkpoint_denied.value.code == "NOT_FOUND"


def test_notify_review_delivers_a_notification_dedupe_safe(harness):
    owner_id, client_id = seed_owner(harness)
    store = _store(harness, owner_id, client_id)
    item = store.create_review_item(
        item_type="profile_confirmation", subject_refs=[], proposal={"summary": "画像待确认"},
        requested_scope="review", idempotency_key=uuid4(),
    )
    handlers = _handlers(harness)
    run_pending_jobs(harness, handlers)  # notify_review + dispatch_notification

    job_rows = [row for row in table_rows(harness, "jobs", owner_id=owner_id)
                if row["job_type"] in {"notify_review", "dispatch_notification"}]
    assert job_rows and all(row["state"] == "succeeded" for row in job_rows), [
        {"job": row["job_type"], "state": row["state"], "code": row["error_code"],
         "summary": row["error_summary"]} for row in job_rows
    ]
    notifications = table_rows(harness, "notifications", owner_id=owner_id)
    assert [row["trigger_type"] for row in notifications] == ["review_item_pending"]
    assert str(notifications[0]["source_object_id"]) == item["review_item_id"]
    assert notifications[0]["state"] in {"queued", "delivered"}
    assert "画像待确认" in notifications[0]["reason"]

    # A second delivery attempt for the same item is deduplicated, not doubled.
    from uuid import uuid5, NAMESPACE_URL
    with harness.factory.begin() as session:
        import sqlalchemy as sa

        session.execute(harness.tables["jobs"].insert().values(
            id=uuid4(), owner_id=owner_id, client_id=None, job_type="notify_review",
            payload_ref=f"review_item:{item['review_item_id']}",
            idempotency_key=uuid5(NAMESPACE_URL, f"test-redeliver:{uuid4()}"),
            state="queued", priority=0, attempts=0, max_attempts=5,
            available_at=datetime.now(timezone.utc), claim_token=0,
        ))
    run_pending_jobs(harness, handlers)
    notifications = table_rows(harness, "notifications", owner_id=owner_id)
    assert len(notifications) == 1


class _Context:
    def progress(self, value, summary):
        return True
