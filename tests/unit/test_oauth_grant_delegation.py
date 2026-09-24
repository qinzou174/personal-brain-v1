"""The MCP-facing OAuth wrapper must delegate the creator self-grant.

Observed 2026-09-25: create_project through MCP silently skipped the
grant because the service's authority is the OAuthBearerAuthority wrapper and
``getattr(wrapper, "grant_project_scope")`` returned None — the capability
existed only for direct callers.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from personal_brain_server.security.oauth_runtime import OAuthBearerAuthority
from personal_brain_server.api.authorized_tools import AuthorizedToolService


def test_oauth_wrapper_delegates_grant_project_scope():
    calls: list[dict] = []

    class Opaque:
        def grant_project_scope(self, context, *, project_id, now=None):
            calls.append({"project_id": project_id, "now": now})
            return {"scope": f"project:{project_id}", "tools": ["project.read", "project.write"]}

    wrapper = OAuthBearerAuthority(
        grant_store=object(), opaque=Opaque(), resource="http://x/mcp",
    )
    context = SimpleNamespace(owner_id="o", client_id="c", authenticated_epoch=1)
    result = wrapper.grant_project_scope(context, project_id="p-1")

    assert result["scope"] == "project:p-1" and len(calls) == 1
    assert calls[0]["project_id"] == "p-1"


def test_create_project_fires_the_grant_through_a_delegating_wrapper():
    grants: list[str] = []

    class Wrapper:
        def authenticate(self, credential):
            return SimpleNamespace(owner_id="o", client_id="c", authenticated_epoch=1)

        def authorize(self, context, *, tool, scope, sensitivity, risk="ordinary"):
            return True

        def grant_project_scope(self, context, *, project_id, now=None):
            grants.append(project_id)

    store = SimpleNamespace(create_project=lambda **_: {
        "status": "accepted", "persistence": "canonical_committed",
        "project_id": str(uuid4()), "source_id": "s", "operation_id": "op",
    })
    service = AuthorizedToolService(Wrapper(), lambda **_: store)
    result = service.create_project(
        credential="t", name="n", purpose="p", requested_scope="projects",
        idempotency_key=uuid4(),
    )
    assert result["status"] == "accepted"
    assert [str(granted) for granted in grants] == [result["project_id"]]


def test_service_without_the_capability_still_creates_projects():
    """Legacy authorities without the method must not break creation."""
    class Legacy:
        def authenticate(self, credential):
            return SimpleNamespace(owner_id="o", client_id="c", authenticated_epoch=1)

        def authorize(self, context, *, tool, scope, sensitivity, risk="ordinary"):
            return True

    store = SimpleNamespace(create_project=lambda **_: {
        "status": "accepted", "persistence": "canonical_committed",
        "project_id": str(uuid4()), "source_id": "s", "operation_id": "op",
    })
    service = AuthorizedToolService(Legacy(), lambda **_: store)
    result = service.create_project(
        credential="t", name="n", purpose="p", requested_scope="projects",
        idempotency_key=uuid4(),
    )
    assert result["status"] == "accepted"