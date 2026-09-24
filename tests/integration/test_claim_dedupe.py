"""D2: duplicate control — extraction rule, daily sweep and owner-approved merge.

The owner profile must not accumulate identical or near-identical claims (the
live Zafiro instance showed one claim three times plus paraphrase clusters).
The rule is deterministic: normalized-identical text or token overlap
>= 0.75 merges (evidence moves, duplicates are superseded with a correction
event, never deleted), stored claim vectors >= 0.85 and token overlap in
[0.5, 0.75) open exactly one ``merge_candidate`` review item, and approving that
item executes the merge through the store. Opposite polarity is never a
duplicate — that is the conflict path.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from activation_support import (
    FakeContext, build_harness, insert_evidence, insert_raw_input, insert_self_claim,
    seed_owner, table_rows,
)

BASE = "倾向把项目、数据和记忆统一收拢到自有服务器体系。"
EXACT_TWIN = "倾向把项目、数据和记忆统一收拢到自有服务器体系"
NEAR_TWIN = "倾向把项目、数据、记忆统一收拢到自有服务器体系。"
POLARITY_TWIN = "不倾向把项目、数据和记忆统一收拢到自有服务器体系。"
PARAPHRASE = "倾向把项目、数据与记忆统一收拢到自有服务器，而非散落在单一 AI 平台。"


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    h = build_harness(tmp_path_factory)
    yield h
    h.drop_schema()


def _sweep(harness, owner_id) -> dict:
    from personal_brain_worker.claim_dedupe import make_dedupe_handler

    handler = make_dedupe_handler(harness.factory, harness.tables)
    return handler(
        {"owner_id": owner_id, "payload_ref": "schedule:dedupe_claims:2026-09-25"}, FakeContext(),
    )


def _index_claim(harness, owner_id, claim_id, text: str, *, axis: int) -> None:
    from personal_brain_infra.search.repository import PostgresSearchRepository

    vector = [0.0] * 1024
    vector[axis] = 1.0
    repository = PostgresSearchRepository(
        harness.factory, harness.tables["search_index_entries"], owner_id=owner_id,
    )
    repository.index(
        target_type="self_claim", target_id=claim_id, authorized_scope="self",
        sensitivity="normal", canonicality="canonical", freshness="fresh", text=text,
        source_links=[f"self_claim:{claim_id}"], vector_model_version="test:dedupe:1024",
        embedding=vector,
    )


def _claims(harness, owner_id) -> dict[UUID, dict]:
    return {row["id"]: row for row in table_rows(harness, "self_claims", owner_id=owner_id)}


def test_sweep_merges_identical_and_near_identical_duplicates_with_a_full_trace(harness):
    owner_id, client_id = seed_owner(harness)
    source = insert_raw_input(harness, owner_id, client_id, text="关于服务器与记忆的偏好")
    survivor = insert_self_claim(
        harness, owner_id, claim=BASE, source_id=source, category="working_style",
        lifecycle_state="active", establishment="explicit",
    )
    insert_evidence(harness, owner_id, claim_id=survivor, source_id=source,
                    observed_at=datetime.now(timezone.utc))
    exact_twin = insert_self_claim(harness, owner_id, claim=EXACT_TWIN, source_id=source,
                                   category="working_style")
    near_twin = insert_self_claim(harness, owner_id, claim=NEAR_TWIN, source_id=source,
                                  category="working_style")
    polarity_twin = insert_self_claim(harness, owner_id, claim=POLARITY_TWIN, source_id=source,
                                      category="working_style")
    _index_claim(harness, owner_id, near_twin, NEAR_TWIN, axis=3)

    result = _sweep(harness, owner_id)

    assert result["merged"] == 2 and result["superseded"] == 2
    claims = _claims(harness, owner_id)
    assert claims[survivor]["lifecycle_state"] == "active"
    merged_event = [event for event in claims[survivor]["correction_events"]
                    if event["type"] == "merged_duplicates"]
    assert len(merged_event) == 1 and set(merged_event[0]["merged_claim_ids"]) == {
        str(exact_twin), str(near_twin),
    }
    for duplicate in (exact_twin, near_twin):
        assert claims[duplicate]["lifecycle_state"] == "superseded"
        assert claims[duplicate]["valid_to"] is not None
        assert any(event["type"] == "superseded_by_duplicate_merge"
                   for event in claims[duplicate]["correction_events"])
    # Opposite polarity is a conflict, not a duplicate.
    assert claims[polarity_twin]["lifecycle_state"] == "candidate"

    evidence_targets = {row["target_id"] for row in table_rows(harness, "evidence", owner_id=owner_id)}
    assert evidence_targets == {survivor}
    index_targets = {row["target_id"] for row in table_rows(
        harness, "search_index_entries", owner_id=owner_id)}
    assert index_targets == set()  # the superseded duplicate stops being served

    replay = _sweep(harness, owner_id)
    assert replay["merged"] == 0 and replay["superseded"] == 0


def test_sweep_opens_one_merge_candidate_for_paraphrases_and_vector_suspects(harness):
    owner_id, client_id = seed_owner(harness)
    source = insert_raw_input(harness, owner_id, client_id, text="关于记忆库的两条近义陈述")
    token_suspect = insert_self_claim(harness, owner_id, claim=BASE, source_id=source,
                                      category="working_style")
    paraphrase = insert_self_claim(harness, owner_id, claim=PARAPHRASE, source_id=source,
                                   category="working_style")
    vector_a = insert_self_claim(harness, owner_id, claim="善用 MCP 作为记忆库", source_id=source,
                                 category="habit")
    vector_b = insert_self_claim(harness, owner_id, claim="在聊天中自主调用 MCP 工具",
                                 source_id=source, category="habit")
    # Token-disjoint paraphrases share no text at all; only their stored vectors
    # know they are near-identical (cosine 0.9 here).
    _index_claim(harness, owner_id, vector_a, "善用 MCP 作为记忆库", axis=0)
    vector_b_vector = [0.0] * 1024
    vector_b_vector[0], vector_b_vector[1] = 0.9, 0.4359
    from personal_brain_infra.search.repository import PostgresSearchRepository

    PostgresSearchRepository(
        harness.factory, harness.tables["search_index_entries"], owner_id=owner_id,
    ).index(
        target_type="self_claim", target_id=vector_b, authorized_scope="self",
        sensitivity="normal", canonicality="canonical", freshness="fresh",
        text="在聊天中自主调用 MCP 工具", source_links=[f"self_claim:{vector_b}"],
        vector_model_version="test:dedupe:1024", embedding=vector_b_vector,
    )

    result = _sweep(harness, owner_id)

    assert result["merged"] == 0 and result["superseded"] == 0
    assert result["suspected_items"] == 2
    items = table_rows(harness, "review_inbox_items", owner_id=owner_id)
    assert len(items) == 2 and {item["item_type"] for item in items} == {"merge_candidate"}
    by_kind = {item["proposal"]["kind"]: item for item in items}
    assert set(by_kind) == {"suspected_duplicate_claim", "suspected_paraphrase"}
    assert set(by_kind["suspected_paraphrase"]["subject_refs"]) == {
        str(vector_a), str(vector_b),
    }
    assert by_kind["suspected_paraphrase"]["proposal"]["similarity"] >= 0.85
    notify_jobs = [job for job in table_rows(harness, "jobs", job_type="notify_review",
                                             owner_id=owner_id)]
    assert len(notify_jobs) == 2 and all(job["state"] == "queued" for job in notify_jobs)
    # Nothing changed by itself: suspected duplicates are the owner's decision.
    claims = _claims(harness, owner_id)
    assert claims[token_suspect]["lifecycle_state"] == "candidate"
    assert claims[paraphrase]["lifecycle_state"] == "candidate"

    replay = _sweep(harness, owner_id)
    assert replay["suspected_items"] == 0  # one item per pair, no inbox flooding


def test_owner_approved_merge_moves_evidence_and_parks_the_duplicate(harness):
    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore

    owner_id, client_id = seed_owner(harness)
    source = insert_raw_input(harness, owner_id, client_id, text="关于记忆库的近义陈述")
    survivor = insert_self_claim(harness, owner_id, claim=BASE, source_id=source,
                                 category="working_style", lifecycle_state="active",
                                 establishment="explicit")
    duplicate = insert_self_claim(harness, owner_id, claim=PARAPHRASE, source_id=source,
                                  category="working_style")
    insert_evidence(harness, owner_id, claim_id=duplicate, source_id=source,
                    observed_at=datetime.now(timezone.utc))
    _index_claim(harness, owner_id, duplicate, PARAPHRASE, axis=5)
    assert _sweep(harness, owner_id)["suspected_items"] == 1
    item = table_rows(harness, "review_inbox_items", owner_id=owner_id)[0]

    store = AuthoritativeStore(harness.factory, owner_id=owner_id, client_id=client_id)
    outcome = store.resolve_review_item(
        item_id=item["id"], expected_version=1, decision="approved",
        idempotency_key=uuid4(),
    )

    assert outcome["merged_claims"] == [str(duplicate)]
    claims = _claims(harness, owner_id)
    assert claims[duplicate]["lifecycle_state"] == "superseded"
    assert any(event["type"] == "merged_duplicates"
               and event.get("review_item_id") == str(item["id"])
               for event in claims[survivor]["correction_events"])
    assert {row["target_id"] for row in table_rows(harness, "evidence", owner_id=owner_id)} == {survivor}
    assert table_rows(harness, "search_index_entries", owner_id=owner_id) == []
    assert table_rows(harness, "review_inbox_items", owner_id=owner_id)[0]["state"] == "approved"

    # The profile view states current beliefs only: no duplicate stands beside it.
    profile = store.get_self_context()
    assert [claim["claim_id"] for claim in profile["claims"]] == [str(survivor)]