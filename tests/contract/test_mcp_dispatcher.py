"""T174: shared MCP lifecycle for stdio and Streamable HTTP."""

from __future__ import annotations


def test_initialize_list_and_call_share_one_authenticated_session():
    from personal_brain_server.protocols.mcp_dispatcher import MCPDispatcher

    calls: list[tuple[str, dict, object]] = []
    dispatcher = MCPDispatcher(
        tool_definitions=[{"name": "search_brain", "description": "search", "inputSchema": {"type": "object"}}],
        invoke=lambda name, arguments, identity: calls.append((name, arguments, identity)) or {"hits": ["one"]},
        resolve_identity=lambda credential: {"client": credential},
    )
    initialized = dispatcher.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
        credential="opaque",
    )
    assert initialized.session_id
    listed = dispatcher.handle(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        session_id=initialized.session_id,
        credential="opaque",
    )
    assert listed.payload["result"]["tools"][0]["name"] == "search_brain"
    called = dispatcher.handle(
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search_brain", "arguments": {"query": "京都"}}},
        session_id=initialized.session_id,
        credential="opaque",
    )
    assert called.payload["result"]["structuredContent"] == {"hits": ["one"]}
    assert calls == [("search_brain", {"query": "京都"}, {"client": "opaque"})]


def test_full_fr099_surface_has_closed_noncredential_input_schemas():
    from personal_brain_server.protocols.tools import FR099_TOOL_NAMES, tool_definitions

    definitions = {item["name"]: item for item in tool_definitions()}
    assert set(definitions) == set(FR099_TOOL_NAMES)
    # 30 -> 32 on 2026-09-25: the review inbox became reachable from a client
    # (list_review_items / resolve_review_item), so the governance loop closes.
    # 32 -> 33: list_projects adds discovery to the projects channel.
    # 33 -> 34: get_entry_content closes "found but not readable" for AI clients.
    assert len(definitions) == 34
    for definition in definitions.values():
        schema = definition["inputSchema"]
        assert schema["type"] == "object" and schema["additionalProperties"] is False
        assert "credential" not in schema["properties"] and "client_id" not in schema["properties"]


def test_session_id_is_not_authority_and_credential_is_rechecked_each_call():
    import pytest

    from personal_brain_domain.common.errors import BrainError
    from personal_brain_server.protocols.mcp_dispatcher import MCPDispatcher

    dispatcher = MCPDispatcher(
        tool_definitions=[], invoke=lambda *_: {},
        resolve_identity=lambda credential: (_ for _ in ()).throw(BrainError("AUTH_INVALID")) if credential == "revoked" else credential,
    )
    session = dispatcher.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
        credential="valid",
    ).session_id
    with pytest.raises(BrainError) as caught:
        dispatcher.handle(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            session_id=session,
            credential="revoked",
        )
    assert caught.value.code == "AUTH_INVALID"


def test_streamable_http_sets_session_and_enforces_origin_and_bearer():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from personal_brain_server.protocols.mcp_dispatcher import MCPDispatcher
    from personal_brain_server.protocols.remote import create_mcp_router

    dispatcher = MCPDispatcher(
        tool_definitions=[], invoke=lambda *_: {}, resolve_identity=lambda token: {"token": token},
    )
    app = FastAPI()
    app.include_router(create_mcp_router(
        dispatcher=dispatcher,
        resource="https://brain.example.test/mcp",
        authorization_server="https://brain.example.test",
        allowed_origins={"https://client.example.test"},
    ))
    client = TestClient(app)
    response = client.post(
        "/mcp",
        headers={
            "Authorization": "Bearer opaque",
            "Origin": "https://client.example.test",
            "MCP-Protocol-Version": "2025-11-25",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
    )
    assert response.status_code == 200
    assert response.headers["MCP-Session-Id"]
    denied = client.post(
        "/mcp",
        headers={"Authorization": "Bearer opaque", "Origin": "https://evil.example.test", "MCP-Protocol-Version": "2025-11-25"},
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    )
    # 403, not 401: a denied Origin is a transport policy refusal, and a client
    # that reads 401 as "my credential is bad" would rotate a valid credential.
    assert denied.status_code == 403
    assert denied.json()["error"]["message"] == "ORIGIN_NOT_ALLOWED"
    discovery = client.get("/.well-known/oauth-protected-resource")
    assert discovery.json()["resource"] == "https://brain.example.test/mcp"


def test_initialize_negotiates_unsupported_version_to_supported_one():
    import pytest

    from personal_brain_domain.common.errors import BrainError
    from personal_brain_server.protocols.mcp_dispatcher import MCPDispatcher, PROTOCOL_VERSION

    dispatcher = MCPDispatcher(
        tool_definitions=[], invoke=lambda *_: {}, resolve_identity=lambda credential: credential,
    )
    negotiated = dispatcher.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
        credential="opaque",
    )
    assert negotiated.payload["result"]["protocolVersion"] == PROTOCOL_VERSION
    assert negotiated.session_id
    with pytest.raises(BrainError) as caught:
        dispatcher.handle(
            {"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {}},
            credential="opaque",
        )
    assert caught.value.code == "VALIDATION_FAILED"


def test_version_header_is_optional_on_initialize_but_required_afterwards():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from personal_brain_server.protocols.mcp_dispatcher import MCPDispatcher, PROTOCOL_VERSION
    from personal_brain_server.protocols.remote import create_mcp_router

    dispatcher = MCPDispatcher(
        tool_definitions=[], invoke=lambda *_: {}, resolve_identity=lambda token: {"token": token},
    )
    app = FastAPI()
    app.include_router(create_mcp_router(
        dispatcher=dispatcher,
        resource="https://brain.example.test/mcp",
        authorization_server="https://brain.example.test",
        allowed_origins={"https://client.example.test"},
    ))
    client = TestClient(app)
    initialized = client.post(
        "/mcp",
        headers={"Authorization": "Bearer opaque"},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
    )
    assert initialized.status_code == 200
    assert initialized.json()["result"]["protocolVersion"] == PROTOCOL_VERSION
    session_id = initialized.headers["MCP-Session-Id"]
    missing = client.post(
        "/mcp",
        headers={"Authorization": "Bearer opaque", "MCP-Session-Id": session_id},
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    )
    assert missing.status_code == 400
    stale = client.post(
        "/mcp",
        headers={
            "Authorization": "Bearer opaque", "MCP-Session-Id": session_id,
            "MCP-Protocol-Version": "2025-06-18",
        },
        json={"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}},
    )
    assert stale.status_code == 400
    accepted = client.post(
        "/mcp",
        headers={
            "Authorization": "Bearer opaque", "MCP-Session-Id": session_id,
            "MCP-Protocol-Version": PROTOCOL_VERSION,
        },
        json={"jsonrpc": "2.0", "id": 4, "method": "tools/list", "params": {}},
    )
    assert accepted.status_code == 200


def test_tool_failure_is_reported_in_band_with_http_200():
    """MCP 2025-11-25: a tool that ran and failed must answer with result.isError.

    A JSON-RPC error (HTTP 400) claims the *request* was malformed; clients then
    cannot tell "your credential is wrong" from "your scope is denied".
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from personal_brain_domain.common.errors import BrainError
    from personal_brain_server.protocols.mcp_dispatcher import MCPDispatcher
    from personal_brain_server.protocols.remote import create_mcp_router

    def invoke(_name, _arguments, _identity):
        raise BrainError("SCOPE_DENIED")

    dispatcher = MCPDispatcher(
        tool_definitions=[{"name": "search_brain", "description": "", "inputSchema": {}}],
        invoke=invoke, resolve_identity=lambda token: {"token": token},
    )
    app = FastAPI()
    app.include_router(create_mcp_router(
        dispatcher=dispatcher, resource="https://brain.example.test/mcp",
        authorization_server="https://brain.example.test", allowed_origins=(),
    ))
    client = TestClient(app)
    initialized = client.post(
        "/mcp", headers={"Authorization": "Bearer opaque"},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2025-11-25"}},
    )
    session_id = initialized.headers["MCP-Session-Id"]
    response = client.post(
        "/mcp",
        headers={"Authorization": "Bearer opaque", "MCP-Session-Id": session_id,
                 "MCP-Protocol-Version": "2025-11-25"},
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
              "params": {"name": "search_brain", "arguments": {}}},
    )
    assert response.status_code == 200
    body = response.json()
    assert "error" not in body
    assert body["result"]["isError"] is True
    assert body["result"]["structuredContent"] == {
        "code": "SCOPE_DENIED", "message": "The requested scope is not permitted.",
    }


def test_not_found_keeps_its_own_jsonrpc_code_and_unknown_method_stays_32601():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from personal_brain_server.protocols.mcp_dispatcher import MCPDispatcher
    from personal_brain_server.protocols.remote import create_mcp_router

    dispatcher = MCPDispatcher(
        tool_definitions=[], invoke=lambda *_: {}, resolve_identity=lambda token: {"token": token},
    )
    app = FastAPI()
    app.include_router(create_mcp_router(
        dispatcher=dispatcher, resource="https://brain.example.test/mcp",
        authorization_server="https://brain.example.test", allowed_origins=(),
    ))
    client = TestClient(app)
    session_id = client.post(
        "/mcp", headers={"Authorization": "Bearer opaque"},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2025-11-25"}},
    ).headers["MCP-Session-Id"]
    unknown = client.post(
        "/mcp",
        headers={"Authorization": "Bearer opaque", "MCP-Session-Id": session_id,
                 "MCP-Protocol-Version": "2025-11-25"},
        json={"jsonrpc": "2.0", "id": 2, "method": "no/such/method", "params": {}},
    )
    assert unknown.status_code == 400
    # NOT_FOUND is a resource answer, not "method not found" — the dispatcher's
    # catch-all for unknown methods is what actually means -32601.
    assert unknown.json()["error"]["code"] == -32004
    assert unknown.json()["error"]["message"] == "NOT_FOUND"


def test_sessions_expire_and_stay_bounded():
    from datetime import datetime, timedelta, timezone

    import pytest

    from personal_brain_domain.common.errors import BrainError
    from personal_brain_server.protocols.mcp_dispatcher import MCPDispatcher

    clock = [datetime(2026, 9, 25, tzinfo=timezone.utc)]
    dispatcher = MCPDispatcher(
        tool_definitions=[], invoke=lambda *_: {}, resolve_identity=lambda credential: credential,
        session_ttl=timedelta(hours=1), max_sessions=2, now=lambda: clock[0],
    )
    first = dispatcher.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-11-25"}}, credential="opaque",
    )
    for index in range(2):
        dispatcher.handle(
            {"jsonrpc": "2.0", "id": 10 + index, "method": "initialize",
             "params": {"protocolVersion": "2025-11-25"}}, credential="opaque",
        )
    with pytest.raises(BrainError) as evicted:
        dispatcher.handle({"jsonrpc": "2.0", "id": 3, "method": "ping"},
                          credential="opaque", session_id=first.session_id)
    assert evicted.value.code == "MCP_SESSION_REQUIRED"

    live = dispatcher.handle(
        {"jsonrpc": "2.0", "id": 4, "method": "initialize",
         "params": {"protocolVersion": "2025-11-25"}}, credential="opaque",
    )
    clock[0] += timedelta(hours=2)
    with pytest.raises(BrainError) as expired:
        dispatcher.handle({"jsonrpc": "2.0", "id": 5, "method": "ping"},
                          credential="opaque", session_id=live.session_id)
    assert expired.value.code == "MCP_SESSION_REQUIRED"


def test_missing_session_asks_for_initialize_with_400_not_401():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from personal_brain_server.protocols.mcp_dispatcher import MCPDispatcher
    from personal_brain_server.protocols.remote import create_mcp_router

    dispatcher = MCPDispatcher(
        tool_definitions=[], invoke=lambda *_: {}, resolve_identity=lambda token: {"token": token},
    )
    app = FastAPI()
    app.include_router(create_mcp_router(
        dispatcher=dispatcher, resource="https://brain.example.test/mcp",
        authorization_server="https://brain.example.test", allowed_origins=(),
    ))
    client = TestClient(app)
    response = client.post(
        "/mcp",
        headers={"Authorization": "Bearer opaque", "MCP-Session-Id": "session-never-issued",
                 "MCP-Protocol-Version": "2025-11-25"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["message"] == "MCP_SESSION_REQUIRED"
    assert body["error"]["code"] == -32000
