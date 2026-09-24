"""Transport-neutral MCP 2025-11-25 request dispatcher."""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from personal_brain_domain.common.errors import BrainError

PROTOCOL_VERSION = "2025-11-25"


@dataclass(frozen=True, slots=True)
class DispatchResult:
    payload: dict[str, Any]
    session_id: str | None = None


class MCPDispatcher:
    """Own MCP lifecycle state while re-authenticating every request."""

    def __init__(
        self,
        *,
        tool_definitions: Sequence[Mapping[str, Any]],
        invoke: Callable[[str, dict[str, Any], Any], Mapping[str, Any]],
        resolve_identity: Callable[[str], Any],
    ) -> None:
        self._tools = [dict(tool) for tool in tool_definitions]
        self._tool_names = {str(tool["name"]) for tool in self._tools}
        self._invoke = invoke
        self._resolve_identity = resolve_identity
        self._sessions: set[str] = set()

    @staticmethod
    def _result(request_id: Any, result: Mapping[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": dict(result)}

    def handle(
        self,
        request: Mapping[str, Any],
        *,
        credential: str,
        session_id: str | None = None,
    ) -> DispatchResult:
        if request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
            raise BrainError("VALIDATION_FAILED")
        identity = self._resolve_identity(credential)
        method = request["method"]
        request_id = request.get("id")
        params = request.get("params") or {}
        if not isinstance(params, Mapping):
            raise BrainError("VALIDATION_FAILED")

        if method == "initialize":
            requested_version = params.get("protocolVersion")
            if not isinstance(requested_version, str) or not requested_version:
                raise BrainError("VALIDATION_FAILED")
            # Version negotiation (MCP 2025-11-25): when the client asks for a
            # version we do not support, answer with the version we do support
            # instead of failing; the client decides whether it can continue.
            new_session = secrets.token_urlsafe(24)
            self._sessions.add(new_session)
            return DispatchResult(
                self._result(request_id, {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "personal-brain", "version": "0.1.0"},
                }),
                session_id=new_session,
            )

        if session_id is None or session_id not in self._sessions:
            raise BrainError("AUTH_INVALID")
        if method == "notifications/initialized":
            return DispatchResult({}, session_id=session_id)
        if method == "ping":
            # MCP 2025-11-25 liveness probe; respond with an empty result.
            return DispatchResult(self._result(request_id, {}), session_id=session_id)
        if method == "tools/list":
            return DispatchResult(
                self._result(request_id, {"tools": self._tools}), session_id=session_id,
            )
        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {})
            if name not in self._tool_names or not isinstance(arguments, dict):
                raise BrainError("VALIDATION_FAILED")
            outcome = dict(self._invoke(str(name), arguments, identity))
            text = json.dumps(outcome, ensure_ascii=False, separators=(",", ":"))
            return DispatchResult(
                self._result(request_id, {
                    "content": [{"type": "text", "text": text}],
                    "structuredContent": outcome,
                    "isError": False,
                }),
                session_id=session_id,
            )
        raise BrainError("NOT_FOUND")
