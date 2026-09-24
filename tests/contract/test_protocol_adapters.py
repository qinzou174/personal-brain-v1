"""Remote and local protocol adapters (T039, FR-075/098/099)."""

import json

import pytest


def test_remote_validates_origin_strictly():
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_server.protocols.remote import validate_origin

    with pytest.raises(BrainError):
        validate_origin("https://evil.example.test", allowed_origins={"https://brain.example.test"})
    with pytest.raises(BrainError):
        validate_origin("null", allowed_origins={"https://brain.example.test"})
    with pytest.raises(BrainError):
        validate_origin("http://brain.example.test", allowed_origins={"https://brain.example.test"})
    assert validate_origin("https://brain.example.test", allowed_origins={"https://brain.example.test"}) == "https://brain.example.test"


def test_stdio_emits_only_jsonrpc_on_stdout(capsys):
    from personal_brain_bridge.stdio import run_stdio_once

    request = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}
    line = run_stdio_once(json.dumps(request), authorized_client_id="local-client")
    response = json.loads(line)
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "local-client" not in line
    assert capsys.readouterr().out == ""
