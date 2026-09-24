"""Protocol-neutral request/success/error envelopes and status lookup (T029)."""

import pytest

from personal_brain_domain.common.errors import BrainError


def test_request_envelope_rejects_credentials_inside_payload():
    from personal_brain_server.protocols.contracts import build_request_envelope

    with pytest.raises(BrainError):
        build_request_envelope(
            request_id="req-1",
            client_id="client-a",
            operation="save_note",
            idempotency_key="key-1",
            requested_scope="personal",
            payload={"content": "note", "credential": "secret-token"},
        )


def test_success_envelope_distinguishes_accepted_from_completed():
    from personal_brain_server.protocols.contracts import build_success_envelope

    completed = build_success_envelope(
        request_id="req-1", status="completed", result={"record_id": "one"}, source_refs=["s1"], warnings=[]
    )
    assert completed["status"] == "completed"
    assert completed["result"] == {"record_id": "one"}
    accepted = build_success_envelope(request_id="req-2", status="accepted", result={"job_ref": "j1"}, source_refs=[], warnings=[])
    assert accepted["status"] == "accepted"
    assert "persistence" not in accepted


def test_operation_status_lookup_tracks_lifecycle():
    from personal_brain_server.protocols.contracts import InMemoryOperationStatusStore

    store = InMemoryOperationStatusStore()
    store.record("op-1", "accepted", result={"job_ref": "j1"})
    store.record("op-1", "completed", result={"record_id": "one"})
    assert store.get("op-1")["status"] == "completed"
    assert store.get("op-1")["result"] == {"record_id": "one"}
    with pytest.raises(BrainError) as caught:
        store.get("missing-op")
    assert caught.value.code == "NOT_FOUND"
