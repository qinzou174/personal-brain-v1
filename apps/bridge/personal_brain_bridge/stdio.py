"""Local stdio MCP transport for the workspace bridge.

FR-075/FR-098: stdout carries only JSON-RPC protocol lines; logs go to stderr.
The adapter authenticates the local client identity and never echoes client
identifiers or private material into protocol responses.
"""

from __future__ import annotations

import json
import math
import sys
from typing import Any, TextIO

from personal_brain_domain.common.errors import BrainError
from personal_brain_server.protocols.mcp_dispatcher import MCPDispatcher
from personal_brain_server.protocols.tools import tool_definitions
from personal_brain_bridge.remote_proxy import RemoteMCPProxy


def sanitize(obj: Any) -> Any:
    """Make a decoded JSON value safe to re-serialize and forward.

    Windows pipes default to a locale codec with surrogateescape, so a
    non-UTF-8 client can inject lone surrogates via stdin; httpx then fails to
    re-encode the request body and the process dies. Replace lone surrogates
    with U+FFFD and non-finite floats (json accepts NaN/Infinity literals,
    httpx forbids them) with None — malformed input must degrade, never kill
    the bridge.
    """
    if isinstance(obj, str):
        try:
            obj.encode("utf-8")
        except UnicodeEncodeError:
            # lone surrogates (surrogateescape artifacts or \uD800 escapes)
            # re-encode via surrogatepass, then invalid bytes become U+FFFD;
            # valid surrogate PAIRS (real astral chars) pass strict encode
            return obj.encode("utf-8", "surrogatepass").decode("utf-8", "replace")
        return obj
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, list):
        return [sanitize(item) for item in obj]
    if isinstance(obj, dict):
        return {key: sanitize(value) for key, value in obj.items()}
    return obj


def _initialize_response(request_id: int) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "protocolVersion": "2025-11-25",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "personal-brain-bridge", "version": "0.1.0"},
        },
    }


def _default_dispatcher() -> MCPDispatcher:
    def unavailable(*_: Any) -> dict[str, Any]:
        raise BrainError("BRAIN_UNAVAILABLE")

    return MCPDispatcher(
        tool_definitions=tool_definitions(),
        invoke=unavailable,
        resolve_identity=lambda credential: credential,
    )


def run_stdio_once(
    request_line: str,
    *,
    authorized_client_id: str,
    dispatcher: MCPDispatcher | None = None,
    session_id: str | None = None,
) -> str:
    """Handle one JSON-RPC request line and return exactly one response line.

    Only ``initialize`` is implemented here; unsupported methods return a safe
    error that never includes the client identity.
    """
    try:
        request = json.loads(request_line)
    except (json.JSONDecodeError, TypeError):
        return json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})

    active = dispatcher or _default_dispatcher()
    try:
        result = active.handle(
            request,
            credential=authorized_client_id,
            session_id=session_id,
        )
        return json.dumps(result.payload)
    except BrainError as error:
        code = -32601 if error.code == "NOT_FOUND" else -32000
        return json.dumps({
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {"code": code, "message": error.code},
        })


def run_stdio_stream(source: TextIO, output: TextIO, *, authorized_client_id: str,
                     remote_proxy: RemoteMCPProxy | None = None) -> int:
    """Serve newline-delimited JSON-RPC until EOF, flushing every response."""
    handled = 0
    dispatcher = _default_dispatcher()
    session_id: str | None = None
    for line in source:
        if not line.strip():
            continue
        request: dict[str, Any] = {}
        try:
            request = sanitize(json.loads(line))
            if remote_proxy is not None:
                response = remote_proxy.handle(request)
                if "id" not in request:
                    # JSON-RPC: a notification (no "id") must never receive a
                    # response line, even when the remote answers 202 with an
                    # empty body — echoing {} desynchronizes strict clients.
                    continue
                if not response:
                    response = {"jsonrpc": "2.0", "id": request.get("id"),
                                "error": {"code": -32000, "message": "BRAIN_UNAVAILABLE"}}
                response_line = json.dumps(sanitize(response))
            else:
                result = dispatcher.handle(
                    request, credential=authorized_client_id, session_id=session_id,
                )
                session_id = result.session_id or session_id
                response_line = json.dumps(sanitize(result.payload))
        except (json.JSONDecodeError, TypeError):
            response_line = json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
        except BrainError as error:
            if "id" not in request:
                # a failed notification still gets no response line
                continue
            code = -32601 if error.code == "NOT_FOUND" else -32000
            response_line = json.dumps({"jsonrpc": "2.0", "id": request.get("id"), "error": {"code": code, "message": error.code}})
        output.write(response_line + "\n")
        output.flush()
        handled += 1
    return handled
