"""Transport-neutral MCP 2025-11-25 request dispatcher."""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Sequence

from personal_brain_domain.common.errors import BrainError

PROTOCOL_VERSION = "2025-11-25"
# Sessions live in-process and are re-authenticated on every request, so they are
# only a lifecycle marker: bounded memory and an explicit expiry keep a restarted
# api from answering "credential invalid" to a client whose session is simply gone.
SESSION_TTL = timedelta(hours=12)
MAX_SESSIONS = 512


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
        session_ttl: timedelta = SESSION_TTL,
        max_sessions: int = MAX_SESSIONS,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._tools = [dict(tool) for tool in tool_definitions]
        self._tool_names = {str(tool["name"]) for tool in self._tools}
        self._invoke = invoke
        self._resolve_identity = resolve_identity
        self._sessions: dict[str, datetime] = {}
        self._session_ttl = session_ttl
        self._max_sessions = max_sessions
        self._now = now or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _result(request_id: Any, result: Mapping[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": dict(result)}

    @staticmethod
    def _tool_error(request_id: Any, code: str, message: str) -> dict[str, Any]:
        """MCP 2025-11-25: a tool that ran and failed reports in-band.

        The transport stays 200 with ``result.isError`` true (a JSON-RPC error
        would tell the client the *request* was malformed); the stable Brain code
        travels in both the machine-readable content and the structured payload.
        """
        body = {"code": code, "message": message}
        return {
            "jsonrpc": "2.0", "id": request_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(body, ensure_ascii=False)}],
                "structuredContent": body,
                "isError": True,
            },
        }

    def _register_session(self) -> str:
        now = self._now()
        for expired in [key for key, seen in self._sessions.items()
                        if now - seen > self._session_ttl]:
            self._sessions.pop(expired, None)
        while len(self._sessions) >= self._max_sessions:
            oldest = min(self._sessions, key=self._sessions.get)
            self._sessions.pop(oldest, None)
        session = secrets.token_urlsafe(24)
        self._sessions[session] = now
        return session

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
            new_session = self._register_session()
            return DispatchResult(
                self._result(request_id, {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "personal-brain", "version": "0.1.0"},
                }),
                session_id=new_session,
            )

        if session_id is None or session_id not in self._sessions:
            # Not a credential problem: the client only has to initialize again
            # (a restarted api forgets in-process sessions by design).
            raise BrainError("MCP_SESSION_REQUIRED")
        if self._now() - self._sessions[session_id] > self._session_ttl:
            self._sessions.pop(session_id, None)
            raise BrainError("MCP_SESSION_REQUIRED")
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
            try:
                outcome = dict(self._invoke(str(name), arguments, identity))
            except BrainError as error:
                # The tool ran and failed (denied, not found, conflict, ...):
                # that is an in-band tool error, not a malformed request.
                return DispatchResult(
                    self._tool_error(request_id, error.code, str(error)),
                    session_id=session_id,
                )
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
