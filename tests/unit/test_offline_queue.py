"""Encrypted offline queue acceptance for T181 / FR-087..FR-088."""

from uuid import uuid4

import pytest


def test_queue_encrypts_payload_deduplicates_and_survives_restart(tmp_path):
    from personal_brain_bridge.pending_store import PendingStore

    path = tmp_path / "private" / "pending.sqlite"
    key = bytes(range(32))
    queue = PendingStore(path, encryption_key=key)
    operation_id = uuid4()
    first = queue.enqueue(operation="save_note", payload={"content": "私人离线笔记"},
                          idempotency_key=operation_id)
    replay = queue.enqueue(operation="save_note", payload={"content": "私人离线笔记"},
                           idempotency_key=operation_id)
    assert replay == first
    assert "私人离线笔记".encode("utf-8") not in path.read_bytes()
    restarted = PendingStore(path, encryption_key=key)
    assert restarted.list_pending()[0].payload == {"content": "私人离线笔记"}


def test_queue_rejects_secrets_before_persistence(tmp_path):
    from personal_brain_bridge.pending_store import PendingStore
    from personal_brain_domain.common.errors import BrainError

    queue = PendingStore(tmp_path / "pending.sqlite", encryption_key=b"k" * 32)
    with pytest.raises(BrainError) as caught:
        queue.enqueue(operation="save_note", payload={"content": "password=never-store-this"},
                      idempotency_key=uuid4())
    assert caught.value.code == "SECRET_REJECTED"
    assert queue.list_pending() == []


def test_queue_replay_is_ordered_and_stops_on_revocation_or_conflict(tmp_path):
    from personal_brain_bridge.pending_store import PendingStore

    queue = PendingStore(tmp_path / "pending.sqlite", encryption_key=b"q" * 32)
    first = queue.enqueue(operation="save_note", payload={"content": "one"}, idempotency_key=uuid4())
    second = queue.enqueue(operation="add_todo", payload={"content": "two"}, idempotency_key=uuid4())
    sent = []
    stopped = queue.replay(send=lambda item: sent.append(item.sequence) or "completed",
                           authority_check=lambda: len(sent) < 1)
    assert stopped == {"status": "stopped", "completed": 1}
    assert sent == [first.sequence]
    conflicted = queue.replay(send=lambda item: "conflict", authority_check=lambda: True)
    assert conflicted == {"status": "conflict", "completed": 0}
    assert queue.list_pending()[0].sequence == second.sequence
    assert queue.list_pending()[0].state == "conflict"


def test_queue_enforces_entry_and_byte_bounds_and_wrong_key_fails_closed(tmp_path):
    from personal_brain_bridge.pending_store import PendingStore
    from personal_brain_domain.common.errors import BrainError

    path = tmp_path / "pending.sqlite"
    queue = PendingStore(path, encryption_key=b"a" * 32, max_entries=1, max_bytes=512)
    queue.enqueue(operation="save_note", payload={"content": "small"}, idempotency_key=uuid4())
    with pytest.raises(BrainError) as caught:
        queue.enqueue(operation="save_note", payload={"content": "second"}, idempotency_key=uuid4())
    assert caught.value.code == "PAYLOAD_TOO_LARGE"
    wrong = PendingStore(path, encryption_key=b"b" * 32, max_entries=1, max_bytes=512)
    with pytest.raises(BrainError) as caught:
        wrong.list_pending()
    assert caught.value.code == "BRAIN_UNAVAILABLE"
