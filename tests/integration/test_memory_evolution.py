"""Δ3: candidate self-claims evolve through scheduled evidence review.

Promotion needs >=3 canonical sources / >=14 days / >=2 contexts / one direct
statement and no contradiction; retention expires unsupported candidates (class A
is exempt) and conflicts land in the review inbox without auto-downgrading.
"""

from __future__ import annotations

import pytest

from activation_support import (
    FakeContext, build_harness, insert_evidence, insert_raw_input, insert_self_claim,
    seed_owner, table_rows, utc_days_ago,
)


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    h = build_harness(tmp_path_factory)
    yield h
    h.drop_schema()


def _handlers(harness):
    from personal_brain_worker.job_handlers import build_job_handlers

    return build_job_handlers(harness.factory, harness.tables, harness.storage)


def _job(owner_id) -> dict:
    return {"owner_id": owner_id, "payload_ref": "schedule:activation:test"}


def test_class_a_candidate_activates_without_extra_evidence(harness):
    owner_id, client_id = seed_owner(harness)
    raw_id = insert_raw_input(harness, owner_id, client_id, text="记住，以后项目时间统一北京时间")
    claim_id = insert_self_claim(
        harness, owner_id, claim="项目时间统一北京时间", source_id=raw_id,
        category="working_style", policy_class="A", establishment="explicit",
    )

    result = _handlers(harness)["promote_candidates"](_job(owner_id), FakeContext())

    row = table_rows(harness, "self_claims", id=claim_id)[0]
    assert row["lifecycle_state"] == "active"
    assert row["establishment"] == "explicit"
    assert any(event.get("type") == "activated" for event in row["correction_events"])
    assert result["activated"] == 1


def test_repeated_preference_promotes_after_evidence_threshold(harness):
    owner_id, client_id = seed_owner(harness)
    sources = [
        insert_raw_input(harness, owner_id, client_id, text=f"第{i}次记录：喜欢喝咖啡")
        for i in range(3)
    ]
    contexts = ("api:knowledge", "api:self", "self:self")
    for index, source_id in enumerate(sources):
        insert_self_claim(
            harness, owner_id, claim="喜欢喝咖啡", source_id=source_id,
            context=contexts[index], created_at=utc_days_ago(20 - index * 10),
        )

    result = _handlers(harness)["promote_candidates"](_job(owner_id), FakeContext())

    rows = table_rows(harness, "self_claims", owner_id=owner_id)
    promoted = [row for row in rows if row["establishment"] == "established"]
    assert len(promoted) == 1
    survivor = promoted[0]
    assert survivor["lifecycle_state"] == "active"
    assert survivor["confidence_inputs"]["evidence_count"] >= 3
    assert survivor["confidence_inputs"]["span_days"] >= 14
    assert any(event.get("type") == "promoted" for event in survivor["correction_events"])
    assert result["promoted"] == 1
    assert len([row for row in rows if row["establishment"] == "candidate"]) == 2

    # Promotion refreshes the retrieval projection for the survivor.
    refresh_jobs = [job for job in table_rows(harness, "jobs", job_type="index_self_claim")
                    if job["payload_ref"] == f"self_claim:{survivor['id']}"]
    assert len(refresh_jobs) == 1


def test_insufficient_span_or_contexts_never_promotes(harness):
    owner_id, client_id = seed_owner(harness)
    for index in range(3):
        source_id = insert_raw_input(harness, owner_id, client_id, text=f"短跨度第{index}次")
        insert_self_claim(
            harness, owner_id, claim="喜欢下雨天", source_id=source_id,
            context="api:knowledge", created_at=utc_days_ago(3 - index),
        )

    result = _handlers(harness)["promote_candidates"](_job(owner_id), FakeContext())

    rows = table_rows(harness, "self_claims", owner_id=owner_id)
    assert all(row["establishment"] == "candidate" for row in rows)
    assert result["promoted"] == 0


def test_evidence_rows_attached_to_one_claim_can_promote_it(harness):
    owner_id, client_id = seed_owner(harness)
    base_source = insert_raw_input(harness, owner_id, client_id, text="第一次记录：喜欢爬山")
    claim_id = insert_self_claim(
        harness, owner_id, claim="喜欢爬山", source_id=base_source, created_at=utc_days_ago(20),
    )
    for index, context in enumerate(("api:self", "cli:knowledge")):
        source_id = insert_raw_input(harness, owner_id, client_id, text=f"再次记录：喜欢爬山({index})")
        insert_evidence(harness, owner_id, claim_id=claim_id, source_id=source_id,
                        observed_at=utc_days_ago(10 - index * 5), context=context)

    result = _handlers(harness)["promote_candidates"](_job(owner_id), FakeContext())

    row = table_rows(harness, "self_claims", id=claim_id)[0]
    assert row["establishment"] == "established" and row["lifecycle_state"] == "active"
    assert result["promoted"] == 1


def test_opposite_polarity_blocks_promotion_and_lands_in_the_inbox(harness):
    owner_id, client_id = seed_owner(harness)
    established_source = insert_raw_input(harness, owner_id, client_id, text="喜欢喝咖啡")
    insert_self_claim(
        harness, owner_id, claim="喜欢喝咖啡", source_id=established_source,
        lifecycle_state="active", establishment="established", created_at=utc_days_ago(30),
    )
    for index, context in enumerate(("api:knowledge", "api:self")):
        source_id = insert_raw_input(harness, owner_id, client_id, text=f"不喜欢喝咖啡({index})")
        insert_self_claim(
            harness, owner_id, claim="不喜欢喝咖啡", source_id=source_id,
            context=context, created_at=utc_days_ago(20 - index * 10),
        )

    promote_result = _handlers(harness)["promote_candidates"](_job(owner_id), FakeContext())
    conflict_result = _handlers(harness)["conflict_scan"](_job(owner_id), FakeContext())

    negatives = [row for row in table_rows(harness, "self_claims", owner_id=owner_id)
                 if row["claim"] == "不喜欢喝咖啡"]
    assert all(row["establishment"] == "candidate" for row in negatives)
    assert promote_result["promoted"] == 0
    assert conflict_result["conflicts"] == 1

    conflicts = table_rows(harness, "conflicts", owner_id=owner_id)
    assert len(conflicts) == 1 and conflicts[0]["state"] == "open"
    assert len(conflicts[0]["participants"]) == 2

    items = table_rows(harness, "review_inbox_items", owner_id=owner_id)
    assert len(items) == 1
    assert items[0]["item_type"] == "conflict" and items[0]["state"] == "open"
    assert len(items[0]["subject_refs"]) == 2
    notify_jobs = [job for job in table_rows(harness, "jobs", job_type="notify_review")
                   if job["payload_ref"] == f"review_item:{items[0]['id']}"]
    assert len(notify_jobs) == 1 and notify_jobs[0]["state"] == "queued"

    # No automatic confidence downgrade (D4=a) and no duplicate inbox items.
    assert _handlers(harness)["conflict_scan"](_job(owner_id), FakeContext())["conflicts"] == 0
    assert len(table_rows(harness, "review_inbox_items", owner_id=owner_id)) == 1


def test_retention_expires_unsupported_candidates_and_exempts_class_a(harness):
    owner_id, client_id = seed_owner(harness)
    stale_source = insert_raw_input(harness, owner_id, client_id, text="过期候选来源")
    stale_id = insert_self_claim(
        harness, owner_id, claim="也许喜欢爬山", source_id=stale_source,
        created_at=utc_days_ago(100),
    )
    rule_source = insert_raw_input(harness, owner_id, client_id, text="A类长期规则")
    rule_id = insert_self_claim(
        harness, owner_id, claim="项目时间统一北京时间", source_id=rule_source,
        category="working_style", policy_class="A", lifecycle_state="active",
        establishment="explicit", created_at=utc_days_ago(200),
    )
    fresh_source = insert_raw_input(harness, owner_id, client_id, text="近期候选来源")
    fresh_id = insert_self_claim(
        harness, owner_id, claim="最近喜欢爵士乐", source_id=fresh_source,
        created_at=utc_days_ago(10),
    )
    established_source = insert_raw_input(harness, owner_id, client_id, text="长期已建立偏好")
    historical_id = insert_self_claim(
        harness, owner_id, claim="偏好纸质笔记", source_id=established_source,
        lifecycle_state="active", establishment="established", created_at=utc_days_ago(200),
    )

    result = _handlers(harness)["retention_sweep"](_job(owner_id), FakeContext())

    rows = {row["id"]: row for row in table_rows(harness, "self_claims", owner_id=owner_id)}
    assert rows[stale_id]["lifecycle_state"] == "expired"
    assert any(event.get("type") == "expired" for event in rows[stale_id]["correction_events"])
    assert rows[rule_id]["lifecycle_state"] == "active"  # class A never ages into expiry
    assert rows[fresh_id]["lifecycle_state"] == "candidate"
    assert rows[historical_id]["lifecycle_state"] == "historical"
    assert result["expired"] == 1 and result["historical"] == 1

    # Idempotent: a second sweep does not rewrite settled rows.
    before = {row["id"]: list(row["correction_events"]) for row in rows.values()}
    second = _handlers(harness)["retention_sweep"](_job(owner_id), FakeContext())
    after = {row["id"]: list(row["correction_events"])
             for row in table_rows(harness, "self_claims", owner_id=owner_id)}
    assert second["expired"] == 0 and second["historical"] == 0
    assert after == before


def test_expired_candidate_is_removed_from_retrieval(harness):
    from personal_brain_infra.search.repository import PostgresSearchRepository

    owner_id, client_id = seed_owner(harness)
    source_id = insert_raw_input(harness, owner_id, client_id, text="将被过期的候选")
    claim_id = insert_self_claim(
        harness, owner_id, claim="曾经喜欢桌游", source_id=source_id, created_at=utc_days_ago(120),
    )
    repository = PostgresSearchRepository(
        harness.factory, harness.tables["search_index_entries"], owner_id=owner_id,
    )
    repository.index(
        target_type="self_claim", target_id=claim_id, authorized_scope="self",
        sensitivity="private", canonicality="canonical", freshness="fresh",
        text="曾经喜欢桌游", source_links=[f"self_claim:{claim_id}"],
    )

    _handlers(harness)["retention_sweep"](_job(owner_id), FakeContext())

    hits = repository.search(query="桌游", authorized_scope="self", sensitivity_ceiling="private")
    assert all(hit["target_id"] != str(claim_id) for hit in hits)