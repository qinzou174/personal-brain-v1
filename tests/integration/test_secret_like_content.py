"""Decision (b), 2026-09-25: secret-like notes stay local and never dead-letter.

A note whose text trips the shared secret filter is still accepted as canonical
raw input, but its content must never leave for an embedding or language model
provider. The index degrades to a keyword-only card carrying the declared
warning ``secret_like_semantic_skipped``, the extract job settles as
``skipped=secret_like_content`` instead of dead-lettering, and the daily digest
replaces the record with a value-free marker.
"""

from __future__ import annotations

import json

import pytest

from activation_support import (
    FakeContext, build_harness, constant_provider, gateway_for, insert_raw_input,
    job_state, local_at, queue_job, run_pending_jobs, seed_owner, table_rows,
)

from personal_brain_domain.common.errors import BrainError
from personal_brain_domain.security.secret_filter import detect_secret

SECRET_LIKE_TEXT = "服务器密码 password: hunter2xyz 不要外传"


class SecretAwareEmbedder:
    """Mirrors VolcengineEmbeddingProvider's local gate without any network."""

    model_version = "test:secret-aware:1024"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(self, text: str, *, timeout_seconds: int = 60) -> list[float]:
        self.calls.append(text)
        detection = detect_secret(
            filename="embedding-input.txt", content_type="text/plain", content=text,
        )
        if detection.matched:
            raise BrainError("SECRET_REJECTED")
        return [0.0] * 1024


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    h = build_harness(tmp_path_factory)
    yield h
    h.drop_schema()


def _handlers(harness, *, gateway=None, embedder=None):
    from personal_brain_worker.job_handlers import build_job_handlers

    return build_job_handlers(
        harness.factory, harness.tables, harness.storage, gateway=gateway, embedder=embedder,
    )


def test_secret_like_note_indexes_keyword_only_and_settles_succeeded(harness):
    owner_id, client_id = seed_owner(harness)
    raw_id = insert_raw_input(harness, owner_id, client_id, text=SECRET_LIKE_TEXT)
    job_id = queue_job(harness, owner_id, job_type="index_raw_input",
                       payload_ref=f"raw_input:{raw_id}")
    embedder = SecretAwareEmbedder()
    handlers = _handlers(harness, gateway=None, embedder=embedder)

    assert run_pending_jobs(harness, handlers) >= 1

    settled = job_state(harness, job_id)
    assert settled["state"] == "succeeded"  # a declared skip, not a dead letter
    assert settled["result_refs"]["warnings"] == ["secret_like_semantic_skipped"]
    assert embedder.calls == [SECRET_LIKE_TEXT]  # the attempt happened locally

    entries = table_rows(harness, "search_index_entries", owner_id=owner_id)
    assert len(entries) == 1
    assert entries[0]["embedding"] is None
    assert entries[0]["vector_model_version"] is None
    assert entries[0]["metadata_filters"]["warnings"] == ["secret_like_semantic_skipped"]

    # The card is still locally retrievable by keyword and declares its skip.
    from personal_brain_infra.search.repository import PostgresSearchRepository

    repository = PostgresSearchRepository(
        harness.factory, harness.tables["search_index_entries"], owner_id=owner_id,
    )
    hits = repository.search(query="密码", authorized_scope="knowledge",
                             sensitivity_ceiling="private")
    assert len(hits) == 1
    assert hits[0]["target_id"] == str(raw_id)
    assert "secret_like_semantic_skipped" in hits[0]["warnings"]

    # The canonical raw text is untouched: nothing was lost or rewritten.
    raw = table_rows(harness, "raw_inputs", id=raw_id)
    assert raw[0]["content_text"] == SECRET_LIKE_TEXT
    assert raw[0]["lifecycle_state"] == "active"


def test_secret_like_note_skips_extraction_without_provider_call(harness):
    owner_id, client_id = seed_owner(harness)
    raw_id = insert_raw_input(harness, owner_id, client_id, text=SECRET_LIKE_TEXT)
    job_id = queue_job(harness, owner_id, job_type="extract_raw_input",
                       payload_ref=f"raw_input:{raw_id}")
    provider = constant_provider(json.dumps({"summary": "不应发生", "candidates": []}))
    handlers = _handlers(harness, gateway=gateway_for(provider))

    assert run_pending_jobs(harness, handlers) >= 1

    settled = job_state(harness, job_id)
    assert settled["state"] == "succeeded"
    assert settled["result_refs"]["skipped"] == "secret_like_content"
    assert provider.calls == []
    assert table_rows(harness, "derived_contents", owner_id=owner_id) == []
    assert table_rows(harness, "self_claims", owner_id=owner_id) == []


def test_non_secret_note_still_indexes_with_embedding_and_extracts(harness):
    owner_id, client_id = seed_owner(harness)
    raw_id = insert_raw_input(harness, owner_id, client_id, text="最近喜欢在傍晚散步")
    index_job = queue_job(harness, owner_id, job_type="index_raw_input",
                          payload_ref=f"raw_input:{raw_id}")
    queue_job(harness, owner_id, job_type="extract_raw_input", payload_ref=f"raw_input:{raw_id}")
    embeddings = SecretAwareEmbedder()
    provider = constant_provider(json.dumps({
        "summary": "用户提到傍晚散步。",
        "candidates": [{"category": "habit", "claim": "用户喜欢傍晚散步",
                        "confidence": "medium", "quote": "喜欢在傍晚散步"}],
    }, ensure_ascii=False))
    handlers = _handlers(harness, gateway=gateway_for(provider), embedder=embeddings)

    assert run_pending_jobs(harness, handlers) >= 1

    assert job_state(harness, index_job)["state"] == "succeeded"
    entries = [row for row in table_rows(harness, "search_index_entries", owner_id=owner_id)
               if row["target_type"] == "raw_input"]
    assert len(entries) == 1 and entries[0]["embedding"] is not None
    assert entries[0]["metadata_filters"]["warnings"] == []
    claim_entries = [row for row in table_rows(harness, "search_index_entries", owner_id=owner_id)
                     if row["target_type"] == "self_claim"]
    assert len(claim_entries) == 1 and claim_entries[0]["embedding"] is not None
    assert len(provider.calls) == 1
    assert len(table_rows(harness, "self_claims", owner_id=owner_id)) == 1


def test_digest_marks_secret_like_records_and_never_sends_them(harness, monkeypatch):
    import personal_brain_worker.digest as digest_module

    owner_id, client_id = seed_owner(harness)
    read_id = insert_raw_input(harness, owner_id, client_id, text="普通笔记：今天读了一篇论文",
                               scope="knowledge", original_at=local_at(2026, 9, 19, 10, 0))
    insert_raw_input(harness, owner_id, client_id, text=SECRET_LIKE_TEXT, scope="knowledge",
                     original_at=local_at(2026, 9, 19, 11, 0))
    monkeypatch.setattr(digest_module, "utcnow", lambda: local_at(2026, 9, 20, 9, 0))
    provider = constant_provider("- 今天读了一篇论文")
    handlers = _handlers(harness, gateway=gateway_for(provider))

    result = handlers["daily_digest"](
        {"owner_id": owner_id, "payload_ref": "schedule:daily_digest:2026-09-20"}, FakeContext())

    assert result["digests"] == 1 and result["secret_excluded"] == 1
    assert len(provider.calls) == 1
    sent = json.dumps(provider.calls[0], ensure_ascii=False)
    assert "今天读了一篇论文" in sent
    assert "hunter2xyz" not in sent  # the secret-like value never left the machine
    assert "疑似凭据内容" in sent     # its place in the day stays navigable
    digests = [row for row in table_rows(harness, "derived_contents", owner_id=owner_id)
               if row["kind"] == "digest"]
    assert len(digests) == 1
    payload = json.loads(harness.storage.read(digests[0]["payload_ref"]).decode("utf-8"))
    assert f"raw_input:{read_id}" in payload["source_links"]


def test_digest_skips_a_scope_made_only_of_secret_like_records(harness, monkeypatch):
    import personal_brain_worker.digest as digest_module

    owner_id, client_id = seed_owner(harness)
    insert_raw_input(harness, owner_id, client_id, text=SECRET_LIKE_TEXT, scope="knowledge",
                     original_at=local_at(2026, 9, 18, 10, 0))
    monkeypatch.setattr(digest_module, "utcnow", lambda: local_at(2026, 9, 19, 9, 0))
    provider = constant_provider("- 不应发生")
    handlers = _handlers(harness, gateway=gateway_for(provider))

    result = handlers["daily_digest"](
        {"owner_id": owner_id, "payload_ref": "schedule:daily_digest:2026-09-19"}, FakeContext())

    assert result["digests"] == 0 and result["secret_skipped_scopes"] == 1
    assert provider.calls == []
    assert [row for row in table_rows(harness, "derived_contents", owner_id=owner_id)
            if row["kind"] == "digest"] == []