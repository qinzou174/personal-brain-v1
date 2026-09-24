"""Contract: schema-declared optional params must be tolerated when omitted.

Regression for the dogfooding demo where checkpoint_task / finalize_task failed
with VALIDATION_FAILED: the tool schemas mark revision / end_revision /
end_dirty_state optional, but the service signatures required them, so a
well-formed client (omitting optionals per schema) hit a TypeError that was
mapped to VALIDATION_FAILED.
"""
from __future__ import annotations

import uuid

import pytest

from personal_brain_server.api.authorized_tools import AuthorizedToolService


class _Ctx:
    owner_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    client_id = uuid.UUID("22222222-2222-2222-2222-222222222222")


class _Auth:
    def authenticate(self, credential: str) -> _Ctx:
        return _Ctx()

    def authorize(self, *args, **kwargs) -> None:
        return None


class _Store:
    def __init__(self, **kwargs) -> None:
        self.calls: list[dict] = []

    def project_of_task(self, task_id: uuid.UUID) -> uuid.UUID:
        # Authority now comes from the task's own project, not the caller scope.
        return uuid.UUID("33333333-3333-3333-3333-333333333333")

    def checkpoint_project_task(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return {"status": "accepted", "task_id": str(kwargs["task_id"])}

    def finalize_project_task(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return {"status": "completed", "task_id": str(kwargs["task_id"])}


def _service(store: _Store) -> AuthorizedToolService:
    return AuthorizedToolService(_Auth(), lambda **kwargs: store)


TASK_ID = uuid.uuid4()
KEY = uuid.uuid4()


def test_checkpoint_task_omits_optional_revision() -> None:
    store = _Store()
    svc = _service(store)
    result = svc.checkpoint_task(
        credential="c", task_id=TASK_ID, completed_work="w", next_step="n",
        problems="", requested_scope="projects", idempotency_key=KEY,
    )
    assert result["status"] == "accepted"
    assert "revision" not in store.calls[0] or store.calls[0].get("revision") is None


def test_checkpoint_task_accepts_explicit_revision() -> None:
    store = _Store()
    svc = _service(store)
    result = svc.checkpoint_task(
        credential="c", task_id=TASK_ID, completed_work="w", next_step="n",
        problems="", revision="main@abc", requested_scope="projects", idempotency_key=KEY,
    )
    assert result["status"] == "accepted"
    assert store.calls[0]["revision"] == "main@abc"


def test_finalize_task_omits_optional_end_revision_and_dirty() -> None:
    store = _Store()
    svc = _service(store)
    result = svc.finalize_task(
        credential="c", task_id=TASK_ID, outcome="completed", verification="v",
        remaining_work="", changed_files=[], requested_scope="projects",
        idempotency_key=KEY,
    )
    assert result["status"] == "completed"


def test_finalize_task_accepts_explicit_end_revision_and_dirty() -> None:
    store = _Store()
    svc = _service(store)
    result = svc.finalize_task(
        credential="c", task_id=TASK_ID, outcome="completed", verification="v",
        remaining_work="", end_revision="main@def", end_dirty_state=True,
        changed_files=[], requested_scope="projects", idempotency_key=KEY,
    )
    assert result["status"] == "completed"
    assert store.calls[0]["end_revision"] == "main@def"
    assert store.calls[0]["end_dirty_state"] is True
