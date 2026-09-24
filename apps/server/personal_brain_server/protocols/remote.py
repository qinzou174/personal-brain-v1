"""Remote HTTPS Streamable-HTTP protocol adapter.

FR-075/FR-098/FR-099: the remote surface authenticates a client, validates the
Origin, and exposes only the authenticated Brain tool interface. No internal
store, worker, or admin surface is ever reachable from a remote client.
"""

from __future__ import annotations

import logging
from typing import Iterable

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse, Response

from personal_brain_domain.common.errors import BrainError
from personal_brain_server.protocols.mcp_dispatcher import MCPDispatcher, PROTOCOL_VERSION

_logger = logging.getLogger("personal_brain.protocol")

# Transport status per stable code. Everything else is a bad request (400); the
# two 401 codes are the only ones that mean "your credential is the problem", so
# clients that key their retry/rotate logic on 401 cannot be misled by an Origin
# refusal or a forgotten MCP session.
_HTTP_STATUS = {
    "AUTH_INVALID": 401, "AUTH_REQUIRED": 401, "CLIENT_REVOKED": 401,
    "ORIGIN_NOT_ALLOWED": 403,
}
# JSON-RPC code per stable code: NOT_FOUND keeps a server-range code of its own
# instead of -32601, which the spec reserves for "method not found" (a deleted
# project is not a missing method).
_JSONRPC_CODE = {"NOT_FOUND": -32004}


def validate_origin(origin: str, *, allowed_origins: Iterable[str]) -> str:
    """Reject any Origin that is not an exact match from the allowlist.

    An empty allowlist denies every Origin-bearing request by design (native MCP
    clients send none); configure ``BRAIN_ALLOWED_ORIGINS`` when a browser-based
    client must connect.
    """
    allowed = frozenset(allowed_origins)
    if origin not in allowed:
        raise BrainError("ORIGIN_NOT_ALLOWED")
    return origin


def create_mcp_router(
    *,
    dispatcher: MCPDispatcher,
    resource: str,
    authorization_server: str,
    allowed_origins: Iterable[str],
) -> APIRouter:
    """Expose discovery and JSON-only Streamable HTTP MCP endpoints."""
    router = APIRouter()
    origin_allowlist = frozenset(allowed_origins)

    @router.get("/.well-known/oauth-protected-resource")
    def protected_resource() -> dict[str, object]:
        return {"resource": resource, "authorization_servers": [authorization_server]}

    @router.post("/mcp")
    async def mcp(
        request: Request,
        authorization: str | None = Header(default=None),
        origin: str | None = Header(default=None),
        mcp_protocol_version: str | None = Header(default=None, alias="MCP-Protocol-Version"),
        mcp_session_id: str | None = Header(default=None, alias="MCP-Session-Id"),
    ) -> Response:
        try:
            if origin is not None:
                validate_origin(origin, allowed_origins=origin_allowlist)
            if mcp_protocol_version is not None and mcp_protocol_version != PROTOCOL_VERSION:
                raise BrainError("VALIDATION_FAILED")
            if not authorization or not authorization.startswith("Bearer "):
                raise BrainError("AUTH_INVALID")
            credential = authorization.removeprefix("Bearer ").strip()
            if not credential:
                raise BrainError("AUTH_INVALID")
            body = await request.json()
            if not isinstance(body, dict):
                raise BrainError("VALIDATION_FAILED")
            # MCP 2025-11-25 requires MCP-Protocol-Version only on requests after
            # initialization; the initialize request negotiates the version via its
            # params instead, so a compliant client may omit the header there.
            if body.get("method") != "initialize" and mcp_protocol_version != PROTOCOL_VERSION:
                raise BrainError("VALIDATION_FAILED")
            result = dispatcher.handle(
                body,
                credential=credential,
                session_id=mcp_session_id,
            )
        except BrainError as error:
            status = _HTTP_STATUS.get(error.code, 400)
            # JSON-RPC 2.0: unknown method/tool is -32601; NOT_FOUND carries its
            # own server-range code; every other rejection uses -32000 with the
            # stable Brain code as the message.
            jsonrpc_code = _JSONRPC_CODE.get(error.code, -32000)
            # Body-free operational log: reason and outcome only, never the
            # request body, credential or client identity (FR-070/FR-073).
            _logger.warning("mcp rejected status=%s code=%s method=%s", status, error.code, request.method)
            return JSONResponse(
                {"jsonrpc": "2.0", "id": None, "error": {"code": jsonrpc_code, "message": error.code}},
                status_code=status,
            )
        except TypeError:
            # A tools/call with missing or unexpected arguments lands here;
            # that is a client validation failure, not a JSON parse error.
            _logger.warning("mcp rejected status=400 code=VALIDATION_FAILED method=%s", request.method)
            return JSONResponse(
                {"jsonrpc": "2.0", "id": None,
                 "error": {"code": -32000, "message": "VALIDATION_FAILED"}},
                status_code=400,
            )
        except ValueError:
            _logger.warning("mcp rejected status=400 code=PARSE_ERROR method=%s", request.method)
            return JSONResponse(
                {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}},
                status_code=400,
            )
        if not result.payload:
            return Response(status_code=202)
        headers = {"MCP-Session-Id": result.session_id} if result.session_id else None
        return JSONResponse(result.payload, headers=headers)

    return router
