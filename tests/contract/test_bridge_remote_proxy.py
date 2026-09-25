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


def test_proxy_forwards_notifications_without_emitting_response_line():
    """JSON-RPC notifications must never receive a response, even when the
    remote answers 202 with an empty body — echoing {} breaks strict clients."""
    import io
    import json

    from personal_brain_bridge.remote_proxy import RemoteMCPProxy
    from personal_brain_bridge.stdio import run_stdio_stream

    methods = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        methods.append(body["method"])
        if body["method"] == "initialize":
            return httpx.Response(200, headers={"MCP-Session-Id": "s1"}, json={
                "jsonrpc": "2.0", "id": body["id"], "result": {},
            })
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"ok": True}})

    proxy = RemoteMCPProxy(
        url="http://127.0.0.1:18081/mcp", credential="secret",
        transport=httpx.MockTransport(handler),
    )
    source = io.StringIO(
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25"}}\n'
        '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}\n'
        '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_todos","arguments":{}}}\n'
    )
    output = io.StringIO()
    assert run_stdio_stream(source, output, authorized_client_id="local", remote_proxy=proxy) == 2
    proxy.close()
    # the notification was still forwarded upstream
    assert methods == ["initialize", "notifications/initialized", "tools/call"]
    lines = output.getvalue().splitlines()
    assert len(lines) == 2
    assert [json.loads(line)["id"] for line in lines] == [1, 2]
    assert all(json.loads(line) != {} for line in lines)


def test_proxy_rejects_public_plain_http_and_empty_credential_file(tmp_path):
    import pytest
    from personal_brain_bridge.remote_proxy import read_credential, validate_remote_url

    with pytest.raises(ValueError):
        validate_remote_url("http://example.com/mcp")
    empty = tmp_path / "credential"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        read_credential(empty)


def test_proxy_sanitizes_lone_surrogates_from_client_and_remote():
    """A Windows-pipe client can inject lone surrogates (gbk+surrogateescape
    stdin) and the remote can echo them back; httpx re-encoding must never
    kill the bridge — both sides degrade to U+FFFD instead."""
    import io
    import json

    from personal_brain_bridge.remote_proxy import RemoteMCPProxy
    from personal_brain_bridge.stdio import run_stdio_stream

    seen_bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_bodies.append(request.content)
        body = json.loads(request.content)
        if body["method"] == "initialize":
            return httpx.Response(200, headers={"MCP-Session-Id": "s1"}, json={
                "jsonrpc": "2.0", "id": body["id"], "result": {},
            })
        # hand-built body: httpx's Response(json=...) would itself reject the
        # lone surrogate, but a real remote CAN emit "\\ud800" escapes
        payload = ('{"jsonrpc":"2.0","id":%d,"result":{"content":'
                   '[{"type":"text","text":"remote \\ud800 payload"}]}}'
                   % body["id"]).encode("ascii")
        return httpx.Response(200, content=payload, headers={"Content-Type": "application/json"})

    proxy = RemoteMCPProxy(
        url="http://127.0.0.1:18081/mcp", credential="secret",
        transport=httpx.MockTransport(handler),
    )
    # "\\ud800" in the wire format: json.loads produces a lone surrogate,
    # exactly what surrogateescape stdin decoding yields for bad bytes.
    source = io.StringIO(
        '{"jsonrpc":"2.0","id":1,"method":"tools/call",'
        '"params":{"name":"search_brain","arguments":{"query":"bad \\ud800 query"}}}\n'
    )
    output = io.StringIO()
    assert run_stdio_stream(source, output, authorized_client_id="local", remote_proxy=proxy) == 1
    proxy.close()
    # forwarded request body is valid UTF-8 with the surrogate neutralized
    forwarded = json.loads(seen_bodies[0].decode("utf-8"))
    query = forwarded["params"]["arguments"]["query"]
    assert query.startswith("bad ") and query.endswith(" query")
    assert not any(0xD800 <= ord(ch) <= 0xDFFF for ch in query)
    # response line written, process alive, surrogate from remote neutralized
    line = json.loads(output.getvalue())
    assert line["id"] == 1
    text = line["result"]["content"][0]["text"]
    assert text.startswith("remote ") and text.endswith(" payload")
    assert not any(0xD800 <= ord(ch) <= 0xDFFF for ch in text)


def test_proxy_replaces_non_finite_float_literals_with_null():
    """json accepts NaN/Infinity literals; httpx's allow_nan=False must never
    see them — they degrade to null at the bridge boundary."""
    import io
    import json

    from personal_brain_bridge.remote_proxy import RemoteMCPProxy
    from personal_brain_bridge.stdio import run_stdio_stream

    seen_bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_bodies.append(request.content)
        body = json.loads(request.content)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {}})

    proxy = RemoteMCPProxy(
        url="http://127.0.0.1:18081/mcp", credential="secret",
        transport=httpx.MockTransport(handler),
    )
    source = io.StringIO(
        '{"jsonrpc":"2.0","id":1,"method":"tools/call",'
        '"params":{"name":"add_expense","arguments":{"amount":NaN}}}\n'
    )
    output = io.StringIO()
    assert run_stdio_stream(source, output, authorized_client_id="local", remote_proxy=proxy) == 1
    proxy.close()
    forwarded = json.loads(seen_bodies[0].decode("utf-8"))
    assert forwarded["params"]["arguments"]["amount"] is None
    assert json.loads(output.getvalue())["id"] == 1
