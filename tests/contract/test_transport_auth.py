"""Red-first MCP transport/auth contracts; synthetic checks are not real-client acceptance."""

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

_REDIRECTS = {"chatgpt-client": frozenset({"https://client.example.test/callback"}),
              "client-a": frozenset({"https://client.example.test/callback"})}


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def test_remote_discovery_binds_one_https_resource_and_auth_server():
    from personal_brain_server.security.oauth import OAuthServer

    server = OAuthServer(
        issuer="https://brain.example.test",
        resource="https://brain.example.test/mcp",
        owner_id="owner-1",
        registered_redirect_uris=_REDIRECTS,
    )
    resource = server.protected_resource_metadata()
    authorization = server.authorization_server_metadata()
    assert resource["resource"] == "https://brain.example.test/mcp"
    assert "https://brain.example.test" in resource["authorization_servers"]
    assert authorization["issuer"] == "https://brain.example.test"
    assert "S256" in authorization["code_challenge_methods_supported"]


def test_authorization_code_requires_exact_redirect_resource_and_pkce():
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_server.security.oauth import OAuthServer

    server = OAuthServer(
        issuer="https://brain.example.test",
        resource="https://brain.example.test/mcp",
        owner_id="owner-1",
        registered_redirect_uris=_REDIRECTS,
    )
    verifier = "v" * 43
    code = server.issue_code(
        client_id="chatgpt-client",
        redirect_uri="https://client.example.test/callback",
        code_challenge=_challenge(verifier),
        code_challenge_method="S256",
        scopes={"knowledge.read"},
        resource="https://brain.example.test/mcp",
        owner_confirmed=True,
    )
    for bad in (
        {"code_verifier": "wrong" * 10},
        {"redirect_uri": "https://client.example.test/callback/"},
        {"resource": "https://other.example.test/mcp"},
    ):
        with pytest.raises(BrainError):
            server.exchange_code(**({
                "code": code,
                "client_id": "chatgpt-client",
                "redirect_uri": "https://client.example.test/callback",
                "code_verifier": verifier,
                "resource": "https://brain.example.test/mcp",
            } | bad))
    token = server.exchange_code(
        code=code,
        client_id="chatgpt-client",
        redirect_uri="https://client.example.test/callback",
        code_verifier=verifier,
        resource="https://brain.example.test/mcp",
    )
    assert token.access_token
    with pytest.raises(BrainError):
        server.exchange_code(
            code=code,
            client_id="chatgpt-client",
            redirect_uri="https://client.example.test/callback",
            code_verifier=verifier,
            resource="https://brain.example.test/mcp",
        )


def test_token_cannot_cross_resource_or_survive_revocation():
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_server.security.oauth import OAuthServer

    server = OAuthServer(
        issuer="https://brain.example.test",
        resource="https://brain.example.test/mcp",
        owner_id="owner-1",
        registered_redirect_uris=_REDIRECTS,
    )
    verifier = "v" * 43
    code = server.issue_code(
        client_id="client-a",
        redirect_uri="https://client.example.test/callback",
        code_challenge=_challenge(verifier),
        code_challenge_method="S256",
        scopes={"knowledge.read"},
        resource="https://brain.example.test/mcp",
        owner_confirmed=True,
    )
    token = server.exchange_code(
        code=code,
        client_id="client-a",
        redirect_uri="https://client.example.test/callback",
        code_verifier=verifier,
        resource="https://brain.example.test/mcp",
    ).access_token
    assert server.verify_token(token, resource="https://brain.example.test/mcp", current_epoch=0).client_id == "client-a"
    with pytest.raises(BrainError):
        server.verify_token(token, resource="https://other.example.test/mcp", current_epoch=0)
    with pytest.raises(BrainError):
        server.verify_token(token, resource="https://brain.example.test/mcp", current_epoch=1)
    server.revoke_client("client-a")
    with pytest.raises(BrainError):
        server.verify_token(token, resource="https://brain.example.test/mcp", current_epoch=1)


def test_oauth_rejects_unregistered_redirect_and_expired_code_and_token():
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_server.security.oauth import OAuthServer

    now = [datetime(2026, 1, 1, tzinfo=timezone.utc)]
    server = OAuthServer(
        issuer="https://brain.example.test", resource="https://brain.example.test/mcp",
        owner_id="owner-1", registered_redirect_uris=_REDIRECTS,
        code_ttl_seconds=30, token_ttl_seconds=60, clock=lambda: now[0],
    )
    verifier = "v" * 43
    with pytest.raises(BrainError):
        server.issue_code(client_id="client-a", redirect_uri="https://evil.example/callback",
                          code_challenge=_challenge(verifier), code_challenge_method="S256",
                          scopes={"knowledge.read"}, resource=server.resource, owner_confirmed=True)
    expired = server.issue_code(client_id="client-a", redirect_uri="https://client.example.test/callback",
                                code_challenge=_challenge(verifier), code_challenge_method="S256",
                                scopes={"knowledge.read"}, resource=server.resource, owner_confirmed=True)
    now[0] += timedelta(seconds=31)
    with pytest.raises(BrainError):
        server.exchange_code(code=expired, client_id="client-a",
                             redirect_uri="https://client.example.test/callback",
                             code_verifier=verifier, resource=server.resource)
    fresh = server.issue_code(client_id="client-a", redirect_uri="https://client.example.test/callback",
                              code_challenge=_challenge(verifier), code_challenge_method="S256",
                              scopes={"knowledge.read"}, resource=server.resource, owner_confirmed=True)
    token = server.exchange_code(code=fresh, client_id="client-a",
                                 redirect_uri="https://client.example.test/callback",
                                 code_verifier=verifier, resource=server.resource).access_token
    server.revoke_token(token)
    with pytest.raises(BrainError):
        server.verify_token(token, resource=server.resource, current_epoch=0)


@pytest.mark.parametrize("origin", ["https://evil.example.test", "null", "http://brain.example.test"])
def test_remote_rejects_untrusted_origin(origin):
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_server.protocols.remote import validate_origin

    with pytest.raises(BrainError):
        validate_origin(origin, allowed_origins={"https://brain.example.test"})


def test_local_stdio_emits_only_jsonrpc_and_keeps_logs_off_stdout(capsys):
    from personal_brain_bridge.stdio import run_stdio_once

    request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}}
    response_line = run_stdio_once(json.dumps(request), authorized_client_id="local-client")
    response = json.loads(response_line)
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "local-client" not in response_line
