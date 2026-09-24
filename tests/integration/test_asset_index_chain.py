"""The upload chain must end in retrieval: parse -> durable index job -> card.

Before this chain existed, an uploaded document was parsed into
``derived_contents`` and then became invisible: nothing projected it into
``search_index_entries``, so the text the user uploaded could never be found.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from activation_support import build_harness, run_pending_jobs, seed_owner, table_rows


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    h = build_harness(tmp_path_factory)
    yield h
    h.drop_schema()


@pytest.fixture(scope="module")
def owner(harness):
    return seed_owner(harness)


def test_uploaded_text_is_parsed_and_indexed(harness, owner):
    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore
    from personal_brain_infra.storage.local import LocalStorage
    from personal_brain_worker.job_handlers import build_job_handlers

    owner_id, client_id = owner
    storage = LocalStorage(Path(harness.data_root) / "asset-chain")
    store = AuthoritativeStore(harness.factory, owner_id=owner_id, client_id=client_id)
    note = store.save_note(content="附件来源", requested_scope="knowledge", idempotency_key=uuid4())
    uploaded = store.upload_asset(
        content="会议记录：决定采用结构化索引与每日摘要。".encode("utf-8"),
        original_name="meeting.txt", media_type="text/plain",
        source_id=UUID(note["record_id"]), idempotency_key=uuid4(), storage=storage,
    )

    handlers = build_job_handlers(harness.factory, harness.tables, storage)
    run_pending_jobs(harness, handlers)  # parse_asset
    run_pending_jobs(harness, handlers)  # index_derived_content

    derived = table_rows(harness, "derived_contents", owner_id=owner_id)
    assert [row["kind"] for row in derived] == ["extracted_text"]
    cards = [row for row in table_rows(harness, "search_index_entries", owner_id=owner_id)
             if row["target_type"] == "derived_content"]
    assert [str(row["target_id"]) for row in cards] == [str(derived[0]["id"])]
    assert cards[0]["authorized_scope"] == "asset"
    assert cards[0]["canonicality"] == "derived"
    # The card is a projection of the *content*, not just of the file name.
    assert "结构化索引" in cards[0]["searchable_text"] or "结构化索引" in str(cards[0].get("metadata_filters"))
    index_jobs = [row for row in table_rows(harness, "jobs", owner_id=owner_id)
                  if row["job_type"] == "index_derived_content"]
    assert [row["state"] for row in index_jobs] == ["succeeded"]


def test_rebuild_index_can_restore_asset_cards(harness, owner):
    """A card lost to a restore or an interrupted job must be rebuildable."""
    from personal_brain_server.admin import rebuild_index

    owner_id, _client_id = owner
    result = rebuild_index(harness.factory, harness.tables, batch_limit=5000)
    assert result["enqueued"] >= 1
    with harness.factory() as session:
        import sqlalchemy as sa

        enqueued = list(session.scalars(sa.select(harness.tables["jobs"].c.payload_ref).where(
            harness.tables["jobs"].c.job_type == "rebuild_index",
            harness.tables["jobs"].c.owner_id == owner_id,
        )))
    assert any(ref.startswith("derived_content:") for ref in enqueued)