"""Local stdio MCP transport for the workspace bridge.

FR-075/FR-098: stdout carries only JSON-RPC protocol lines; logs go to stderr.
The adapter authenticates the local client identity and never echoes client
identifiers or private material into protocol responses.
"""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from personal_brain_domain.common.errors import BrainError
from personal_brain_server.protocols.mcp_dispatcher import MCPDispatcher
from personal_brain_server.protocols.tools import tool_definitions
from personal_brain_bridge.remote_proxy import RemoteMCPProxy


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
            request = json.loads(line)
            if remote_proxy is not None:
                response_line = json.dumps(remote_proxy.handle(request))
            else:
                result = dispatcher.handle(
                    request, credential=authorized_client_id, session_id=session_id,
                )
                session_id = result.session_id or session_id
                response_line = json.dumps(result.payload)
        except (json.JSONDecodeError, TypeError):
            response_line = json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
        except BrainError as error:
            code = -32601 if error.code == "NOT_FOUND" else -32000
            response_line = json.dumps({"jsonrpc": "2.0", "id": request.get("id"), "error": {"code": code, "message": error.code}})
        output.write(response_line + "\n")
        output.flush()
        handled += 1
    return handled
