"""Regression for ISSUE-LT-003: save_note/add_todo must reject empty content."""
import uuid

import pytest

from personal_brain_domain.common.errors import BrainError


class _Authority:
    def __init__(self):
        self.calls = []

    def authenticate(self, credential):
        assert credential == "opaque"
        return SimpleNamespace(owner_id=uuid.uuid4(), client_id=uuid.uuid4())

    def authorize(self, context, **kwargs):
        self.calls.append(kwargs)


class SimpleNamespace:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _make_service():
    from personal_brain_server.api.authorized_tools import AuthorizedToolService
    return AuthorizedToolService(
        _Authority(), lambda **kw: _NoopStore(), storage=None,
        search_factory=None, model_gateway=None, embedding_provider=None,
    )


class _NoopStore:
    def save_note(self, **kw):
        return {"ok": True}

    def add_todo(self, **kw):
        return {"ok": True}


def test_save_note_rejects_empty_content():
    service = _make_service()
    with pytest.raises(BrainError) as exc:
        service.save_note(credential="opaque", content="  ", requested_scope="knowledge",
                          idempotency_key=uuid.uuid4())
    assert exc.value.code == "VALIDATION_FAILED"


def test_add_todo_rejects_empty_content():
    service = _make_service()
    with pytest.raises(BrainError) as exc:
        service.add_todo(credential="opaque", content="", requested_scope="todo",
                         idempotency_key=uuid.uuid4())
    assert exc.value.code == "VALIDATION_FAILED"


def test_save_note_accepts_nonempty_content():
    service = _make_service()
    result = service.save_note(credential="opaque", content="有效笔记", requested_scope="knowledge",
                               idempotency_key=uuid.uuid4())
    assert result == {"ok": True}