"""Local stdio bridge forwards the real MCP lifecycle without exposing credentials."""

import io
import json

import httpx


def test_proxy_forwards_initialize_session_list_and_call_without_leaking_credential():
    from personal_brain_bridge.remote_proxy import RemoteMCPProxy
    from personal_brain_bridge.stdio import run_stdio_stream

    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append((body["method"], request.headers.get("MCP-Session-Id"), request.headers["Authorization"]))
        if body["method"] == "initialize":
            return httpx.Response(200, headers={"MCP-Session-Id": "session-one"}, json={
                "jsonrpc": "2.0", "id": body["id"], "result": {"protocolVersion": "2025-11-25"},
            })
        if body["method"] == "tools/list":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"tools": []}})
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {
            "content": [{"type": "text", "text": "ok"}], "isError": False,
        }})

    secret = "never-print-this-credential"
    proxy = RemoteMCPProxy(
        url="http://127.0.0.1:18081/mcp", credential=secret,
        transport=httpx.MockTransport(handler),
    )
    source = io.StringIO(
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25"}}\n'
        '{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n'
        '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"list_todos","arguments":{}}}\n'
    )
    output = io.StringIO()
    assert run_stdio_stream(source, output, authorized_client_id="local", remote_proxy=proxy) == 3
    proxy.close()
    assert seen == [
        ("initialize", None, f"Bearer {secret}"),
        ("tools/list", "session-one", f"Bearer {secret}"),
        ("tools/call", "session-one", f"Bearer {secret}"),
    ]
    assert secret not in output.getvalue()
    assert [json.loads(line)["id"] for line in output.getvalue().splitlines()] == [1, 2, 3]


def test_proxy_rejects_public_plain_http_and_empty_credential_file(tmp_path):
    import pytest
    from personal_brain_bridge.remote_proxy import read_credential, validate_remote_url

    with pytest.raises(ValueError):
        validate_remote_url("http://example.com/mcp")
    empty = tmp_path / "credential"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        read_credential(empty)
