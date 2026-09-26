"""D1 completion: the governance loop closes from a client credential.

``create_deletion_plan`` persists a preview plus a version-bound single-use
confirmation item; ``list_review_items`` shows it; ``resolve_review_item``
(approved) executes the deletion through the store. Without the explicit review
grant on the data scope the same call is still SCOPE_DENIED, so least privilege
is preserved. This is the loop a client could not complete before 2026-09-25:
create → see → confirm → delete.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from activation_support import build_harness, insert_raw_input, seed_owner, table_rows


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    h = build_harness(tmp_path_factory)
    yield h
    h.drop_schema()


def _client_service(harness):
    """A real AuthorizedToolService bound to a real credential for one test owner."""
    from personal_brain_domain.security.clients import Client, issue_credential
    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore
    from personal_brain_infra.security.authority import PersistedAuthority
    from personal_brain_server.api.authorized_tools import AuthorizedToolService

    owner_id, client_id = seed_owner(harness)
    with harness.factory.begin() as session:
        session.execute(harness.tables["clients"].update().where(
            harness.tables["clients"].c.id == client_id,
        ).values(
            scopes=["knowledge", "review"],
            allowed_tools=["knowledge.write", "review.write", "review.read"],
        ))
    client = Client(
        id=str(client_id), owner_id=str(owner_id), status="active", permission_epoch=1,
        allowed_scopes=("knowledge", "review"),
        allowed_tools=("knowledge.write", "review.write", "review.read"),
    )
    # The initial least-privilege profile a real provisioning run writes: content
    # writes on the content scope, review inbox on the review scope only.
    for tool, scope in (("knowledge.write", "knowledge"),
                        ("review.read", "review"), ("review.write", "review")):
        with harness.factory.begin() as session:
            session.execute(harness.tables["permission_grants"].insert().values(
                id=uuid4(), client_id=client_id, effect="allow", scope_pattern=scope,
                tool_pattern=tool, sensitivity_ceiling="private",
                effective_from=datetime.now(timezone.utc), effective_to=None,
                issuer="test", reason="initial profile",
            ))
    token, credential = issue_credential(client, now=datetime.now(timezone.utc))
    with harness.factory.begin() as session:
        session.execute(harness.tables["credentials"].insert().values(
            id=uuid4(), client_id=client_id, verifier=credential.verifier,
            issued_at=credential.issued_at, expires_at=None, revoked_at=None,
            overlap_deadline=None,
        ))
    authority = PersistedAuthority(harness.factory, harness.tables)
    service = AuthorizedToolService(
        authority,
        lambda *, owner_id, client_id: AuthoritativeStore(
            harness.factory, owner_id=owner_id, client_id=client_id,
        ),
    )
    return service, token, owner_id, client_id


def test_deletion_loop_is_denied_without_the_review_grant(harness):
    from personal_brain_domain.common.errors import BrainError

    service, token, owner_id, client_id = _client_service(harness)
    raw_id = insert_raw_input(harness, owner_id, client_id, text="没有治理授权的记录")

    with pytest.raises(BrainError) as denied:
        service.create_deletion_plan(
            credential=token, targets=[["raw_input", str(raw_id)]], dependents={},
            requested_scope="knowledge", idempotency_key=uuid4(),
        )
    assert denied.value.code == "SCOPE_DENIED"
    assert table_rows(harness, "deletion_plans", owner_id=owner_id) == []


def test_deletion_loop_create_see_confirm_and_delete(harness):
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_server.admin import set_review_access

    service, token, owner_id, client_id = _client_service(harness)
    raw_id = insert_raw_input(harness, owner_id, client_id, text="待清理的重复记录")
    set_review_access(
        harness.factory, harness.tables, client_id=client_id, scope="knowledge",
        access="write", confirmed_client_id=client_id, confirmed_scope="knowledge",
    )

    plan = service.create_deletion_plan(
        credential=token, targets=[["raw_input", str(raw_id)]], dependents={},
        requested_scope="knowledge", idempotency_key=uuid4(),
    )

    # ER-06: the gate is answered with the pending plan, not with a dead end.
    assert plan["confirmation_required"] is True
    assert plan["execution_state"] == "preview" and plan["confirmation_state"] == "pending"
    assert plan["review_item_id"]

    inbox = service.list_review_items(credential=token)
    assert [item["review_item_id"] for item in inbox["items"]] == [plan["review_item_id"]]
    item = inbox["items"][0]
    assert item["item_type"] == "deletion_confirmation"
    assert item["version"] == 1 and item["expires_at"] is not None

    pending = service.get_deletion_plan(credential=token, plan_id=plan["plan_id"])
    assert pending["confirmation_state"] == "pending"
    assert table_rows(harness, "raw_inputs", id=raw_id)[0]["lifecycle_state"] == "active"

    outcome = service.resolve_review_item(
        credential=token, item_id=plan["review_item_id"], expected_version=1,
        decision="approved", idempotency_key=uuid4(),
    )

    assert outcome["decision"] == "approved"
    assert table_rows(harness, "raw_inputs", id=raw_id)[0]["lifecycle_state"] == "deleted"
    settled = service.get_deletion_plan(credential=token, plan_id=plan["plan_id"])
    assert settled["confirmation_state"] == "confirmed"
    assert settled["execution_state"] == "completed"
    assert table_rows(harness, "deletion_actions", owner_id=owner_id)
    assert [row for row in table_rows(harness, "jobs", owner_id=owner_id)
            if row["job_type"] == "reconcile_deletion"]
    # B-02: state=None lists every state, so the settled (approved) item still
    # appears — the loop invariant is that no *open* item remains.
    assert service.list_review_items(credential=token, state="open")["items"] == []

    # Single use: the same confirmation cannot be replayed (R9: the
    # idempotent "already resolved" state).
    with pytest.raises(BrainError) as replay:
        service.resolve_review_item(
            credential=token, item_id=plan["review_item_id"], expected_version=1,
            decision="approved", idempotency_key=uuid4(),
        )
    assert replay.value.code == "ALREADY_RESOLVED"