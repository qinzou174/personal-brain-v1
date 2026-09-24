"""Contract: which authority each retrieval/task tool actually exercises.

Two production-visible asymmetries are pinned here:
* ``answer_brain`` used to authorize ``knowledge.read@<scope>`` while
  ``search_brain`` used ``search.read``, so every non-knowledge scope answered
  SCOPE_DENIED for questions but fine for searches.
* ``checkpoint_task``/``finalize_task`` used a caller-supplied scope, which let a
  client holding the broad ``projects`` scope write into any project.
"""

from __future__ import annotations

import uuid

from personal_brain_server.api.authorized_tools import AuthorizedToolService


class _Ctx:
    owner_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    client_id = uuid.UUID("22222222-2222-2222-2222-222222222222")


class _Auth:
    def __init__(self) -> None:
        self.authorizations: list[tuple[str, str]] = []

    def authenticate(self, credential: str) -> _Ctx:
        return _Ctx()

    def authorize(self, context, *, tool: str, scope: str, sensitivity: str, **kwargs) -> None:
        self.authorizations.append((tool, scope))


class _Repository:
    def search(self, **_kwargs):
        return []


class _Gateway:
    def execute(self, *_args, **_kwargs) -> dict:
        return {"text": "一句话回答", "model": "test-model"}


class _Store:
    def __init__(self, **kwargs) -> None:
        self.calls: list[dict] = []

    def project_of_task(self, task_id: uuid.UUID) -> uuid.UUID:
        return uuid.UUID("33333333-3333-3333-3333-333333333333")

    def checkpoint_project_task(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return {"status": "accepted", "task_id": str(kwargs["task_id"])}

    def finalize_project_task(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return {"status": "accepted", "task_id": str(kwargs["task_id"])}


def _service(auth: _Auth, store: _Store) -> AuthorizedToolService:
    return AuthorizedToolService(
        auth, lambda **kwargs: store,
        search_factory=lambda **kwargs: _Repository(),
        model_gateway=_Gateway(),
    )


def test_answer_brain_authorizes_like_search_brain() -> None:
    auth = _Auth()
    service = _service(auth, _Store())
    service.answer_brain(credential="c", query="这个月花了多少", requested_scope="finance")
    assert ("search.read", "finance") in auth.authorizations
    assert not [item for item in auth.authorizations if item[0] == "knowledge.read"]


def test_task_writes_authorize_against_the_tasks_project() -> None:
    auth = _Auth()
    store = _Store()
    service = _service(auth, store)
    task_id = uuid.uuid4()
    service.checkpoint_task(
        credential="c", task_id=task_id, completed_work="w", next_step="n",
        problems="", requested_scope="projects", idempotency_key=uuid.uuid4(),
    )
    service.finalize_task(
        credential="c", task_id=task_id, outcome="o", verification="v", remaining_work="",
        changed_files=[], requested_scope="projects", idempotency_key=uuid.uuid4(),
    )
    scopes = {scope for _tool, scope in auth.authorizations}
    assert scopes == {"project:33333333-3333-3333-3333-333333333333"}
    assert "projects" not in scopes