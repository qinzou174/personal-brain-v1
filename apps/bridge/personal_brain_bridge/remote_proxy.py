"""Credential-safe stdio-to-remote Streamable HTTP MCP proxy."""

from __future__ import annotations

import ipaddress
from pathlib import Path
from urllib.parse import urlparse

import httpx

from personal_brain_domain.common.errors import BrainError
from personal_brain_server.protocols.mcp_dispatcher import PROTOCOL_VERSION


def validate_remote_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.hostname:
        return url.rstrip("/")
    if parsed.scheme == "http" and parsed.hostname:
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            if parsed.hostname == "localhost":
                return url.rstrip("/")
        else:
            if address.is_private or address.is_loopback:
                return url.rstrip("/")
    raise ValueError("remote MCP URL must use HTTPS or private/loopback HTTP")


def read_credential(path: str | Path) -> str:
    credential_path = Path(path).resolve(strict=True)
    credential = credential_path.read_text(encoding="utf-8").strip()
    if not credential:
        raise ValueError("credential file is empty")
    return credential


class RemoteMCPProxy:
    def __init__(self, *, url: str, credential: str,
                 transport: httpx.BaseTransport | None = None, timeout: float = 30.0) -> None:
        self._url = validate_remote_url(url)
        self._credential = credential
        self._session_id: str | None = None
        self._client = httpx.Client(transport=transport, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    # Transport failures can surface as httpx.HTTPError, but stale keep-alive
    # sockets (idle-dropped tunnels) may leak raw OSError/RuntimeError from
    # httpcore on some platforms. Retry once on a fresh connection — request
    # bodies are byte-identical, so server-side idempotency keys dedupe writes.
    _TRANSPORT_ERRORS = (httpx.HTTPError, OSError, RuntimeError)

    def handle(self, request: dict) -> dict:
        headers = {
            "Authorization": f"Bearer {self._credential}",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
            "Content-Type": "application/json",
        }
        if self._session_id:
            headers["MCP-Session-Id"] = self._session_id
        try:
            response = self._client.post(self._url, json=request, headers=headers)
        except self._TRANSPORT_ERRORS:
            try:
                response = self._client.post(self._url, json=request, headers=headers)
            except self._TRANSPORT_ERRORS as error:
                raise BrainError("BRAIN_UNAVAILABLE") from error
        if response.status_code == 202:
            return {}
        try:
            payload = response.json()
        except ValueError as error:
            raise BrainError("BRAIN_UNAVAILABLE") from error
        if not isinstance(payload, dict):
            raise BrainError("BRAIN_UNAVAILABLE")
        session = response.headers.get("MCP-Session-Id")
        if session:
            self._session_id = session
        return payload
