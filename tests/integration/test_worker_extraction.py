"""Δ2: save_note's extract job performs a real bounded LLM extraction.

The extract handler must derive B-class candidates (never canonical facts), keep
the raw input untouched, stay fail-closed without a provider, respect the daily
LLM quota, replay idempotently and treat malformed model output as an honest,
bounded, retryable failure.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

import sqlalchemy as sa
import pytest

from activation_support import (
    FakeContext, build_harness, constant_provider, gateway_for, insert_raw_input,
    job_state, queue_job, run_pending_jobs, seed_owner, table_rows,
)

_EXTRACTION_JSON = json.dumps({
    "summary": "用户说自己最近喜欢喝咖啡。",
    "candidates": [{
        "category": "preference", "claim": "用户喜欢喝咖啡",
        "confidence": "medium", "quote": "最近喜欢喝咖啡",
    }],
}, ensure_ascii=False)


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    h = build_harness(tmp_path_factory)
    yield h
    h.drop_schema()


def _handlers(harness, *, gateway=None, quota: int = 200):
    from personal_brain_worker.job_handlers import build_job_handlers

    return build_job_handlers(
        harness.factory, harness.tables, harness.storage,
        gateway=gateway, embedder=None, llm_daily_quota=quota,
    )


def _extract_job(owner_id, raw_id) -> dict:
    return {"owner_id": owner_id, "payload_ref": f"raw_input:{raw_id}"}


def test_extract_without_provider_skips_without_fabrication(harness):
    owner_id, client_id = seed_owner(harness)
    raw_id = insert_raw_input(harness, owner_id, client_id, text="今天路过一家新咖啡馆")
    handlers = _handlers(harness, gateway=None)

    result = handlers["extract_raw_input"](_extract_job(owner_id, raw_id), FakeContext())

    assert result["extracted"] == 0
    assert result["skipped"] == "provider_unavailable"
    assert table_rows(harness, "derived_contents", owner_id=owner_id) == []
    assert table_rows(harness, "self_claims", owner_id=owner_id) == []


def test_extract_persists_derived_candidates_evidence_and_index_jobs(harness):
    owner_id, client_id = seed_owner(harness)
    raw_id = insert_raw_input(
        harness, owner_id, client_id, text="最近喜欢喝咖啡，每天早上一杯拿铁",
    )
    provider = constant_provider(_EXTRACTION_JSON)
    handlers = _handlers(harness, gateway=gateway_for(provider))
    context = FakeContext()

    result = handlers["extract_raw_input"](_extract_job(owner_id, raw_id), context)

    assert result["extracted"] == 1 and result["dropped"] == 0
    assert len(provider.calls) == 1
    sent = json.dumps(provider.calls[0], ensure_ascii=False)
    assert "每天早上一杯拿铁" in sent  # the real raw text reached the bounded call

    derived = table_rows(harness, "derived_contents", owner_id=owner_id)
    assert len(derived) == 1
    row = derived[0]
    assert row["kind"] == "description" and row["state"] == "active"
    assert row["canonicality"] == "derived" and row["target_type"] == "raw_input"
    assert str(row["target_id"]) == str(raw_id)
    payload = harness.storage.read(row["payload_ref"])
    stored = json.loads(payload.decode("utf-8"))
    assert stored["summary"] == "用户说自己最近喜欢喝咖啡。"

    claims = table_rows(harness, "self_claims", owner_id=owner_id)
    assert len(claims) == 1
    claim = claims[0]
    assert claim["category"] == "preference" and claim["claim"] == "用户喜欢喝咖啡"
    assert claim["policy_class"] == "B"
    assert claim["lifecycle_state"] == "candidate" and claim["establishment"] == "candidate"
    assert claim["review"] == "none"
    assert str(claim["source_id"]) == str(raw_id)
    assert claim["context"] == "api:knowledge"
    assert claim["confidence_inputs"]["confidence"] == "medium"

    evidence = table_rows(harness, "evidence", owner_id=owner_id)
    assert len(evidence) == 1
    assert evidence[0]["target_type"] == "self_claim"
    assert str(evidence[0]["target_id"]) == str(claim["id"])
    assert evidence[0]["stance"] == "supports" and str(evidence[0]["source_id"]) == str(raw_id)

    with harness.factory() as session:
        edges = session.execute(
            sa.select(harness.tables["derivation_edges"]).where(
                harness.tables["derivation_edges"].c.owner_id == owner_id,
            )
        ).mappings().all()
    roles = {(edge["derived_type"], edge["role"]) for edge in edges}
    assert ("derived_content", "extracted_from") in roles
    assert ("self_claim", "inferred_from") in roles

    index_jobs = table_rows(harness, "jobs", job_type="index_self_claim", owner_id=owner_id)
    assert len(index_jobs) == 1
    assert index_jobs[0]["payload_ref"] == f"self_claim:{claim['id']}"
    assert index_jobs[0]["state"] == "queued"

    # The canonical raw input keeps its own identity and lifecycle.
    raw_rows = table_rows(harness, "raw_inputs", id=raw_id)
    assert raw_rows[0]["canonicality"] == "canonical"
    assert raw_rows[0]["lifecycle_state"] == "active"
    assert context.progress_notes[-1][0] == 100


def test_extract_replays_existing_derivation_without_second_call(harness):
    owner_id, client_id = seed_owner(harness)
    raw_id = insert_raw_input(harness, owner_id, client_id, text="我习惯用键盘快捷键")
    provider = constant_provider(_EXTRACTION_JSON)
    handlers = _handlers(harness, gateway=gateway_for(provider))

    handlers["extract_raw_input"](_extract_job(owner_id, raw_id), FakeContext())
    replay = handlers["extract_raw_input"](_extract_job(owner_id, raw_id), FakeContext())

    assert replay["skipped"] == "already_extracted"
    assert len(provider.calls) == 1
    assert len(table_rows(harness, "derived_contents", owner_id=owner_id)) == 1
    assert len(table_rows(harness, "self_claims", owner_id=owner_id)) == 1


def test_extract_merges_a_duplicate_candidate_instead_of_creating_a_second_row(harness):
    """D2: the same claim must not become a second candidate row."""
    from activation_support import insert_evidence, insert_self_claim

    owner_id, client_id = seed_owner(harness)
    existing_source = insert_raw_input(harness, owner_id, client_id,
                                       text="之前已经记过一条相似偏好")
    existing_id = insert_self_claim(
        harness, owner_id, claim="用户喜欢喝咖啡", source_id=existing_source,
        category="preference",
    )
    insert_evidence(harness, owner_id, claim_id=existing_id, source_id=existing_source,
                    observed_at=datetime.now(timezone.utc))
    raw_id = insert_raw_input(harness, owner_id, client_id, text="最近喜欢喝咖啡，每天早上一杯拿铁")
    handlers = _handlers(harness, gateway=gateway_for(constant_provider(_EXTRACTION_JSON)))

    result = handlers["extract_raw_input"](_extract_job(owner_id, raw_id), FakeContext())

    assert result["extracted"] == 0 and result["merged"] == 1
    claims = table_rows(harness, "self_claims", owner_id=owner_id)
    assert len(claims) == 1 and claims[0]["id"] == existing_id
    assert any(event["type"] == "duplicate_candidate_merged"
               for event in claims[0]["correction_events"])
    evidence_rows = table_rows(harness, "evidence", owner_id=owner_id)
    assert {row["target_id"] for row in evidence_rows} == {existing_id}
    assert {str(row["source_id"]) for row in evidence_rows} == {
        str(existing_source), str(raw_id),
    }
    # No second index job: the surviving claim carries the merged evidence.
    assert table_rows(harness, "jobs", job_type="index_self_claim", owner_id=owner_id) == []


def test_extract_respects_daily_quota_and_reports_the_reason(harness):
    owner_id, client_id = seed_owner(harness)
    raw_id = insert_raw_input(harness, owner_id, client_id, text="配额测试记录")
    from datetime import datetime, timezone
    for _ in range(2):
        queue_job(harness, owner_id, job_type="extract_raw_input",
                  payload_ref=f"raw_input:{raw_id}", state="succeeded",
                  started_at=datetime.now(timezone.utc))
    provider = constant_provider(_EXTRACTION_JSON)
    handlers = _handlers(harness, gateway=gateway_for(provider), quota=1)

    result = handlers["extract_raw_input"](_extract_job(owner_id, raw_id), FakeContext())

    assert result == {"extracted": 0, "skipped": "daily_quota_exceeded", "quota": 1}
    assert provider.calls == []
    assert table_rows(harness, "derived_contents", owner_id=owner_id) == []


def test_extract_malformed_model_output_is_retryable_not_silent(harness):
    from personal_brain_worker.runtime import JobExecutionError

    owner_id, client_id = seed_owner(harness)
    raw_id = insert_raw_input(harness, owner_id, client_id, text="无法解析输出测试")
    handlers = _handlers(harness, gateway=gateway_for(constant_provider("抱歉，我无法按要求输出。")))

    with pytest.raises(JobExecutionError) as caught:
        handlers["extract_raw_input"](_extract_job(owner_id, raw_id), FakeContext())
    assert caught.value.code == "BRAIN_UNAVAILABLE" and caught.value.retryable is True
    assert table_rows(harness, "derived_contents", owner_id=owner_id) == []


def test_extract_job_runs_through_the_durable_poller_and_settles_succeeded(harness):
    owner_id, client_id = seed_owner(harness)
    raw_id = insert_raw_input(harness, owner_id, client_id, text="走完整作业链路的记录")
    job_id = queue_job(harness, owner_id, job_type="extract_raw_input",
                       payload_ref=f"raw_input:{raw_id}")
    handlers = _handlers(harness, gateway=gateway_for(constant_provider(_EXTRACTION_JSON)))

    assert run_pending_jobs(harness, handlers) >= 1

    settled = job_state(harness, job_id)
    assert settled["state"] == "succeeded"
    assert settled["result_refs"]["extracted"] == 1
    assert len(table_rows(harness, "self_claims", owner_id=owner_id)) == 1