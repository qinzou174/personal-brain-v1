"""Contract tests: full-text fetch for search hits (AI-consumer readability).

The MCP surface could find entries but had no way to read one in full —
search_brain returns a 300-char head excerpt and answer_brain honestly reports
missing evidence. These tests pin the new `get_entry_content` operation:
authorization rides on the ROW's own scope via ``search.read`` (no client
re-provisioning), sensitivity beyond the caller's ceiling is an honest
NOT_FOUND, and search responses hydrate match-centered excerpts.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from personal_brain_domain.common.errors import BrainError


class RecordingAuthority:
    def __init__(self, *, allowed: set[str] | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.allowed = allowed
        self.owner_id, self.client_id = uuid4(), uuid4()

    def authenticate(self, credential: str):
        assert credential == "opaque"
        return SimpleNamespace(owner_id=self.owner_id, client_id=self.client_id, authenticated_epoch=1)

    def authorize(self, context, *, tool: str, scope: str, sensitivity: str, risk: str = "ordinary", now=None):
        self.calls.append((tool, scope))
        if self.allowed is not None and tool not in self.allowed:
            raise BrainError("SCOPE_DENIED")
        return True


class StubSearch:
    def __init__(self, hits):
        self._hits = hits
        self.searches: list[dict] = []

    def search(self, **kwargs):
        self.searches.append(kwargs)
        return [dict(hit) for hit in self._hits]


class StubStore:
    """Fake store: only the methods the service paths under test touch."""

    def __init__(self, *, entry_row=None):
        self.entry_row = entry_row
        self.entry_calls: list[dict] = []

    def get_entry_content(self, entry_id, *, storage=None, sensitivity_ceiling="private"):
        self.entry_calls.append({"entry_id": entry_id, "ceiling": sensitivity_ceiling})
        return self.entry_row


def _service(authority, *, hits=None, entry_row=None):
    from personal_brain_server.api.authorized_tools import AuthorizedToolService

    store = StubStore(entry_row=entry_row)
    search = StubSearch(hits or [])
    service = AuthorizedToolService(
        authority, lambda **_kwargs: store, search_factory=lambda **_kwargs: search,
    )
    return service, search, store


_ENTRY = {
    "entry_id": "11111111-1111-1111-1111-111111111111",
    "target_type": "raw_input",
    "target_id": "22222222-2222-2222-2222-222222222222",
    "scope": "knowledge",
    "sensitivity": "personal",
    "canonicality": "canonical",
    "text": "【结论笔记·需求】「历史上的今天」日常日志设计\n\n一、需求\n用户每天会讲当天经历。" * 12,
    "source_links": ["raw_input:22222222-2222-2222-2222-222222222222"],
}


def test_get_entry_content_returns_full_text_and_authorizes_row_scope():
    authority = RecordingAuthority()
    service, _search, store = _service(authority, entry_row=dict(_ENTRY))
    result = service.get_entry_content(credential="opaque", entry_id=uuid4())
    assert result["text"].startswith("【结论笔记·需求】")
    assert len(result["text"]) > 300, "full text, not the 300-char excerpt"
    assert result["scope"] == "knowledge"
    # authorization lands on the row's own scope after the owner-safe lookup
    # (checkpoint_task precedent: never trust a caller-declared scope)
    assert authority.calls == [("search.read", "knowledge")]
    assert store.entry_calls[0]["ceiling"] == "private"


def test_get_entry_content_denied_without_search_read_on_row_scope():
    authority = RecordingAuthority(allowed={"knowledge.read"})
    service, _search, _store = _service(authority, entry_row=dict(_ENTRY))
    with pytest.raises(BrainError) as caught:
        service.get_entry_content(credential="opaque", entry_id=uuid4())
    assert caught.value.code == "SCOPE_DENIED"


def test_get_entry_content_absent_entry_is_not_found():
    authority = RecordingAuthority()
    service, _search, _store = _service(authority, entry_row=None)
    with pytest.raises(BrainError) as caught:
        service.get_entry_content(credential="opaque", entry_id=uuid4())
    assert caught.value.code == "NOT_FOUND"


def test_get_entry_content_rejects_unknown_ceiling():
    authority = RecordingAuthority()
    service, _search, store = _service(authority, entry_row=dict(_ENTRY))
    with pytest.raises(BrainError) as caught:
        service.get_entry_content(credential="opaque", entry_id=uuid4(), sensitivity_ceiling="secret")
    assert caught.value.code == "VALIDATION_FAILED"
    assert store.entry_calls == [], "invalid input must not touch the store"


# ---------------------------------------------------------------------------
# match-centered excerpt hydration on search responses
# ---------------------------------------------------------------------------


def _long_document() -> str:
    filler = "这是一段与查询无关的背景叙述，用于把关键信息推到文档深处。" * 12
    return filler + "关键事实：2026-09-25 带小猫去看病。" + filler


def test_search_brain_hydrates_match_centered_excerpt():
    entry_id = uuid4()
    hit = {
        "entry_id": str(entry_id), "target_type": "raw_input",
        "target_id": "22222222-2222-2222-2222-222222222222",
        "scope": "knowledge", "excerpt": "这是一段与查询无关的背景叙述，用于把关键信息推到文档深处。"[:300],
        "score": 0.03, "freshness": "fresh", "canonicality": "canonical",
        "source_links": [], "warnings": [], "vector_model_version": None,
        "ranking_reasons": ["rrf"],
    }
    authority = RecordingAuthority(allowed={"search.read"})
    full_text = _long_document()
    service, _search, _store = _service(
        authority, hits=[hit],
        entry_row={**_ENTRY, "entry_id": str(entry_id), "text": full_text},
    )
    result = service.search_brain(credential="opaque", query="带小猫去看病", requested_scope="knowledge")
    excerpt = result["hits"][0]["excerpt"]
    assert "带小猫去看病" in excerpt, "the matched region must appear in the excerpt"
    assert excerpt.index("带小猫去看病") < len(excerpt) / 2, "excerpt should center on the match"
    assert len(excerpt) <= 340, "hydrated snippet stays bounded"


def test_search_brain_excerpt_falls_back_without_token_match():
    entry_id = uuid4()
    original_excerpt = " completely unrelated head text that stays as-is when nothing matches "
    hit = {
        "entry_id": str(entry_id), "target_type": "raw_input",
        "target_id": "22222222-2222-2222-2222-222222222222",
        "scope": "knowledge", "excerpt": original_excerpt,
        "score": 0.02, "freshness": "fresh", "canonicality": "canonical",
        "source_links": [], "warnings": [], "vector_model_version": None,
        "ranking_reasons": ["rrf"],
    }
    authority = RecordingAuthority(allowed={"search.read"})
    service, _search, _store = _service(
        authority, hits=[hit],
        entry_row={**_ENTRY, "entry_id": str(entry_id), "text": "纯语义命中的文档，没有查询词的字面出现。" * 30},
    )
    result = service.search_brain(credential="opaque", query="带小猫去看病", requested_scope="knowledge")
    assert result["hits"][0]["excerpt"] == original_excerpt


def test_search_brain_survives_hydration_failures():
    """A gone source (or a store without the new method) must never break search."""
    entry_id = uuid4()
    hit = {
        "entry_id": str(entry_id), "target_type": "raw_input",
        "target_id": "22222222-2222-2222-2222-222222222222",
        "scope": "knowledge", "excerpt": "kept", "score": 0.02, "freshness": "fresh",
        "canonicality": "canonical", "source_links": [], "warnings": [],
        "vector_model_version": None, "ranking_reasons": ["rrf"],
    }
    authority = RecordingAuthority(allowed={"search.read"})
    store = StubStore(entry_row=None)  # source gone -> resolver returns None
    from personal_brain_server.api.authorized_tools import AuthorizedToolService
    service = AuthorizedToolService(
        authority, lambda **_kwargs: store, search_factory=lambda **_kwargs: StubSearch([hit]),
    )
    result = service.search_brain(credential="opaque", query="带小猫去看病", requested_scope="knowledge")
    assert result["hits"][0]["excerpt"] == "kept"


# ---------------------------------------------------------------------------
# snippet builder (pure function)
# ---------------------------------------------------------------------------


def test_build_snippet_centers_on_earliest_token_and_bounds_length():
    from personal_brain_domain.retrieval.snippets import build_snippet

    text = _long_document()
    snippet = build_snippet(text, "带小猫去看病")
    assert snippet is not None and "带小猫去看病" in snippet
    assert snippet.index("带小猫去看病") < len(snippet) / 2
    assert len(snippet) <= 340


def test_build_snippet_returns_none_without_any_token_hit():
    from personal_brain_domain.retrieval.snippets import build_snippet

    assert build_snippet("完全无关的内容" * 40, "带小猫去看病") is None


def test_build_snippet_survives_surrogates_and_garbage():
    from personal_brain_domain.retrieval.snippets import build_snippet

    assert build_snippet("bad \ud800 query content", "带小猫") in (None, "bad \ufffd query content")
