"""Contract-fixed read authorization for search_brain / context / project search.

tool-contracts.md names the governing tool per read operation: `search.read` for
`search_brain`, `context.read` for `get_brain_context`, `project.read:<id>` for
`search_project`, and `knowledge.read` for `answer_brain`. These tests pin that
mapping and the fail-closed behaviour for an ungranted scope.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from personal_brain_domain.common.errors import BrainError


class RecordingAuthority:
    """Records every authorize call and can deny a tool the client lacks."""

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
        return self._hits


class StubStore:
    def __init__(self, *, totals=None, todos=None):
        self._totals, self._todos = totals or {"totals": []}, todos or []

    def get_expense_summary(self, *, currency=None):
        return dict(self._totals)

    def list_todos(self):
        return list(self._todos)


def _service(authority, *, hits=None, totals=None, todos=None, gateway=None):
    from personal_brain_server.api.authorized_tools import AuthorizedToolService

    search = StubSearch(hits or [])
    store = StubStore(totals=totals, todos=todos)
    service = AuthorizedToolService(
        authority, lambda **_kwargs: store, search_factory=lambda **_kwargs: search,
        model_gateway=gateway,
    )
    return service, search, store


def test_search_brain_authorizes_search_read_on_requested_scope():
    authority = RecordingAuthority()
    service, search, _store = _service(authority, hits=[{"excerpt": "x", "source_links": ["raw_input:1"]}])
    result = service.search_brain(credential="opaque", query="青石计划", requested_scope="knowledge")
    assert result["authority"] == "hybrid" and result["hits"]
    assert authority.calls == [("search.read", "knowledge"), ("search.read", "knowledge")]
    assert search.searches[0]["authorized_scope"] == "knowledge"


@pytest.mark.parametrize("scope", ["todo", "finance", "self", "diary"])
def test_search_brain_reaches_every_granted_content_scope(scope):
    """The defect F1: non-knowledge scopes must be searchable, not denied."""
    authority = RecordingAuthority(allowed={"search.read"})
    service, search, _store = _service(authority, hits=[{"excerpt": "hit", "source_links": []}])
    result = service.search_brain(credential="opaque", query="随便搜", requested_scope=scope)
    assert result["hits"], f"{scope} search must return hits"
    assert authority.calls[0] == ("search.read", scope)
    assert search.searches[0]["authorized_scope"] == scope


def test_search_brain_denied_before_index_access_without_search_read():
    authority = RecordingAuthority(allowed={"knowledge.read"})
    service, search, _store = _service(authority)
    with pytest.raises(BrainError) as caught:
        service.search_brain(credential="opaque", query="青石计划", requested_scope="knowledge")
    assert caught.value.code == "SCOPE_DENIED"
    assert search.searches == [], "denied read must not touch the index"


def test_get_brain_context_authorizes_context_read():
    authority = RecordingAuthority()
    service, _search, _store = _service(authority, hits=[{"excerpt": "e", "warnings": []}])
    service.get_brain_context(credential="opaque", intent="当前计划", requested_scope="knowledge")
    assert [tool for tool, _scope in authority.calls] == ["context.read", "context.read"]
    assert authority.calls[0][1] == "knowledge"


def test_search_project_authorizes_project_read_scope():
    authority = RecordingAuthority()
    service, search, _store = _service(authority, hits=[])
    project_id = uuid4()
    service.search_project(credential="opaque", project_id=project_id, query="模块")
    assert authority.calls == [
        ("project.read", f"project:{project_id}"),
        ("project.read", f"project:{project_id}"),
    ]
    assert search.searches[0]["authorized_scope"] == f"project:{project_id}"


def test_answer_brain_keeps_knowledge_read_and_rechecks_around_model_call():
    from personal_brain_infra.models.gateway import ModelCard, ModelGateway

    authority = RecordingAuthority(allowed={"knowledge.read"})
    gateway = ModelGateway(
        provider=lambda payload: {"text": "依据证据", "model": payload["model"]},
        card=ModelCard(name="m", version="v1", dimensions=0, tokenizer="t",
                       sensitivity="private", max_input_tokens=100, allowed_context_keys=("sources",)),
        max_calls=1,
    )
    service, _search, _store = _service(
        authority, hits=[{"excerpt": "证据", "source_links": ["raw_input:1"], "warnings": []}], gateway=gateway,
    )
    result = service.answer_brain(credential="opaque", query="问题", requested_scope="knowledge")
    assert result["grounded"] is True
    assert {tool for tool, _scope in authority.calls} == {"knowledge.read"}
    assert len(authority.calls) >= 3, "ER-06 rechecks before source read, external call and response"


def test_search_brain_exact_routes_stay_inside_the_authorized_scope():
    authority = RecordingAuthority(allowed={"search.read"})
    service, _search, store = _service(authority, totals={"totals": [{"currency": "CNY", "total": "38.0000"}]})
    result = service.search_brain(credential="opaque", query="本月总额多少", requested_scope="finance")
    assert result["authority"] == "exact" and result["totals"][0]["total"] == "38.0000"
    assert {tool for tool, _scope in authority.calls} == {"search.read"}


def test_provisioned_client_receives_per_scope_search_and_context_read_grants(tmp_path):
    import sqlalchemy as sa
    from sqlalchemy.orm import Session, sessionmaker

    from personal_brain_server.admin import DEFAULT_TOOLS, provision_client

    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    common = lambda: (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    sa.Table("owners", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True), *common())
    sa.Table(
        "clients", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String, nullable=False), sa.Column("client_type", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False), sa.Column("scopes", sa.JSON, nullable=False),
        sa.Column("allowed_tools", sa.JSON, nullable=False),
        sa.Column("permission_epoch", sa.Integer, nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)), *common(),
    )
    sa.Table(
        "credentials", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("client_id", sa.Uuid(as_uuid=True), nullable=False), sa.Column("verifier", sa.Text, nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)), sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("overlap_deadline", sa.DateTime(timezone=True)), *common(),
    )
    sa.Table(
        "permission_grants", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("client_id", sa.Uuid(as_uuid=True), nullable=False), sa.Column("effect", sa.String, nullable=False),
        sa.Column("scope_pattern", sa.String, nullable=False), sa.Column("tool_pattern", sa.String, nullable=False),
        sa.Column("sensitivity_ceiling", sa.String, nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True)), sa.Column("issuer", sa.String, nullable=False),
        sa.Column("reason", sa.String), *common(),
    )
    sa.Table(
        "audit_events", metadata, sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=False), sa.Column("client_id", sa.Uuid(as_uuid=True)),
        sa.Column("correlation_id", sa.Uuid(as_uuid=True), nullable=False), sa.Column("action", sa.String, nullable=False),
        sa.Column("tool", sa.String), sa.Column("effective_scope", sa.String), sa.Column("target_category", sa.String),
        sa.Column("target_id", sa.Uuid(as_uuid=True)), sa.Column("outcome", sa.String, nullable=False),
        sa.Column("error_code", sa.String), sa.Column("duration_ms", sa.Integer, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False), sa.Column("risk", sa.String, nullable=False),
        sa.Column("authorization_decision", sa.String),
    )
    metadata.create_all(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)

    provisioned = provision_client(
        factory, metadata.tables, display_name="contract-test", client_type="stdio",
        credential_file=tmp_path / "credential",
    )
    with factory() as session:
        rows = session.execute(sa.select(
            metadata.tables["permission_grants"].c.tool_pattern,
            metadata.tables["permission_grants"].c.scope_pattern,
        )).all()
    pairs = {(tool, scope) for tool, scope in rows}
    assert "search.read" in DEFAULT_TOOLS and "context.read" in DEFAULT_TOOLS
    for scope in ("knowledge", "finance", "todo", "self", "asset", "projects"):
        assert ("search.read", scope) in pairs, f"missing search.read on {scope}"
        assert ("context.read", scope) in pairs, f"missing context.read on {scope}"
    with factory() as session:
        tools = session.scalar(sa.select(metadata.tables["clients"].c.allowed_tools))
    assert {"search.read", "context.read"} <= set(tools)
    engine.dispose()
