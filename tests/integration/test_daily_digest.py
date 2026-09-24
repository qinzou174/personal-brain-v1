"""Δ4: daily digest (per scope, previous local day) and proactive health notices.

The digest is a navigation layer: it must persist as derived content, be
retrievable with full source traceability, never fabricate an empty day, and the
health check must notify about dead-letter jobs exactly once per cooldown.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
import pytest

from activation_support import (
    FakeContext, build_harness, constant_provider, gateway_for, insert_raw_input, job_state,
    local_at, queue_job, run_pending_jobs, seed_owner, table_rows,
)

_SUMMARY = "- 用户记录了两条知识笔记\n- 用户记录了一笔餐饮支出"


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    h = build_harness(tmp_path_factory)
    yield h
    h.drop_schema()


def _handlers(harness, *, gateway=None):
    from personal_brain_worker.job_handlers import build_job_handlers

    return build_job_handlers(
        harness.factory, harness.tables, harness.storage, gateway=gateway, embedder=None,
    )


def _pin_digest_clock(monkeypatch, fixed_utc):
    import personal_brain_worker.digest as digest_module

    monkeypatch.setattr(digest_module, "utcnow", lambda: fixed_utc)


def test_digest_summarizes_previous_local_day_per_scope_with_full_sources(harness, monkeypatch):
    owner_id, client_id = seed_owner(harness)
    knowledge_one = insert_raw_input(harness, owner_id, client_id, text="知识笔记一",
                                     scope="knowledge", original_at=local_at(2026, 9, 20, 10, 0))
    knowledge_two = insert_raw_input(harness, owner_id, client_id, text="知识笔记二",
                                     scope="knowledge", original_at=local_at(2026, 9, 20, 21, 0))
    finance_one = insert_raw_input(harness, owner_id, client_id, text="午餐 38 元",
                                   scope="finance", original_at=local_at(2026, 9, 20, 12, 0))
    today_one = insert_raw_input(harness, owner_id, client_id, text="今天的新笔记",
                                 scope="knowledge", original_at=local_at(2026, 9, 21, 9, 0))
    provider = constant_provider(_SUMMARY)
    _pin_digest_clock(monkeypatch, local_at(2026, 9, 21, 10, 0))
    handlers = _handlers(harness, gateway=gateway_for(provider))

    result = handlers["daily_digest"]({"owner_id": owner_id, "payload_ref": "schedule:daily_digest:2026-09-21"},
                                      FakeContext())

    assert result["digests"] == 2 and set(result["scopes"]) == {"knowledge", "finance"}
    assert len(provider.calls) == 2  # one bounded call per scope, not per note

    digests = table_rows(harness, "derived_contents", owner_id=owner_id)
    assert len(digests) == 2 and all(row["kind"] == "digest" for row in digests)
    by_scope = {}
    for row in digests:
        assert row["canonicality"] == "derived" and row["state"] == "active"
        payload = json.loads(harness.storage.read(row["payload_ref"]).decode("utf-8"))
        by_scope[payload["scope"]] = (row, payload)
    knowledge_row, knowledge_payload = by_scope["knowledge"]
    finance_row, finance_payload = by_scope["finance"]
    assert knowledge_payload["summary"] == _SUMMARY
    assert set(knowledge_payload["source_links"]) == {f"raw_input:{knowledge_one}",
                                                      f"raw_input:{knowledge_two}"}
    assert finance_payload["source_links"] == [f"raw_input:{finance_one}"]
    assert f"raw_input:{today_one}" not in json.dumps(by_scope, ensure_ascii=False, default=str)

    with harness.factory() as session:
        edges = [dict(row) for row in session.execute(sa.select(harness.tables["derivation_edges"]).where(
            harness.tables["derivation_edges"].c.owner_id == owner_id,
        )).mappings().all()]
    summarized = {(str(edge["source_id"]), str(edge["derived_id"])) for edge in edges
                  if edge["role"] == "summarized_from"}
    assert (str(knowledge_one), str(knowledge_row["id"])) in summarized
    assert (str(knowledge_two), str(knowledge_row["id"])) in summarized
    assert (str(finance_one), str(finance_row["id"])) in summarized

    # The digest is a real retrieval target with traceable source links.
    from personal_brain_infra.search.repository import PostgresSearchRepository

    repository = PostgresSearchRepository(
        harness.factory, harness.tables["search_index_entries"], owner_id=owner_id,
    )
    hits = repository.search(query="知识笔记", authorized_scope="knowledge",
                             sensitivity_ceiling="private")
    digest_hits = [hit for hit in hits if hit["target_type"] == "derived_content"]
    assert len(digest_hits) == 1
    assert set(digest_hits[0]["source_links"]) == {f"raw_input:{knowledge_one}",
                                                   f"raw_input:{knowledge_two}"}

    # Re-running the same day is a replay, not a duplicate.
    replay = handlers["daily_digest"]({"owner_id": owner_id, "payload_ref": "schedule:daily_digest:2026-09-21"},
                                      FakeContext())
    assert replay["digests"] == 0 and replay["skipped_scopes"] == 2
    assert len(table_rows(harness, "derived_contents", owner_id=owner_id)) == 2


def test_digest_skips_empty_window_without_provider_call(harness, monkeypatch):
    owner_id, _client_id = seed_owner(harness)
    provider = constant_provider(_SUMMARY)
    _pin_digest_clock(monkeypatch, local_at(2026, 9, 25, 10, 0))
    handlers = _handlers(harness, gateway=gateway_for(provider))

    result = handlers["daily_digest"]({"owner_id": owner_id, "payload_ref": "schedule:daily_digest:2026-09-25"},
                                      FakeContext())

    assert result["skipped"] == "empty_window"
    assert provider.calls == []
    assert table_rows(harness, "derived_contents", owner_id=owner_id) == []


def test_digest_without_provider_reports_honestly_and_persists_nothing(harness, monkeypatch):
    owner_id, client_id = seed_owner(harness)
    insert_raw_input(harness, owner_id, client_id, text="无模型时的记录",
                     original_at=local_at(2026, 9, 23, 11, 0))
    _pin_digest_clock(monkeypatch, local_at(2026, 9, 24, 10, 0))
    handlers = _handlers(harness, gateway=None)

    result = handlers["daily_digest"]({"owner_id": owner_id, "payload_ref": "schedule:daily_digest:2026-09-24"},
                                      FakeContext())

    assert result == {"skipped": "provider_unavailable"}
    assert table_rows(harness, "derived_contents", owner_id=owner_id) == []


def test_digest_runs_through_the_scheduler_and_worker_loop(harness, monkeypatch):
    from personal_brain_worker.scheduler import PeriodicScheduler

    owner_id, client_id = seed_owner(harness)
    insert_raw_input(harness, owner_id, client_id, text="调度链路摘要记录",
                     original_at=local_at(2026, 9, 19, 10, 0))
    # A past instant: the scheduler stamps available_at, and a queued job is only
    # claimable once it is actually due.
    fixed = local_at(2026, 9, 20, 9, 0)
    _pin_digest_clock(monkeypatch, fixed)
    scheduler = PeriodicScheduler(harness.factory, harness.tables, now=lambda: fixed, tick_seconds=0)
    assert scheduler.tick() >= 1
    handlers = _handlers(harness, gateway=gateway_for(constant_provider(_SUMMARY)))

    assert run_pending_jobs(harness, handlers) >= 1

    digests = [row for row in table_rows(harness, "derived_contents", owner_id=owner_id)
               if row["kind"] == "digest"]
    assert len(digests) == 1
    digest_jobs = [job for job in table_rows(harness, "jobs", owner_id=owner_id)
                   if job["job_type"] == "daily_digest"]
    assert len(digest_jobs) == 1 and digest_jobs[0]["state"] == "succeeded"


def test_health_check_notifies_on_failures_and_stays_quiet_when_healthy(harness):
    owner_id, _client_id = seed_owner(harness)
    handlers = _handlers(harness, gateway=None)

    healthy = handlers["health_check"]({"owner_id": owner_id, "payload_ref": "schedule:health_check:x"},
                                       FakeContext())
    assert healthy["failed_jobs"] == 0 and healthy["notified"] is False
    assert table_rows(harness, "notifications", owner_id=owner_id) == []

    queue_job(harness, owner_id, job_type="index_todo", payload_ref="todo:x", state="dead_letter")
    result = handlers["health_check"]({"owner_id": owner_id, "payload_ref": "schedule:health_check:x"},
                                       FakeContext())

    assert result["failed_jobs"] == 1 and result["notified"] is True
    notifications = table_rows(harness, "notifications", owner_id=owner_id)
    assert len(notifications) == 1
    notification = notifications[0]
    assert notification["trigger_type"] == "brain_health_failure"
    assert notification["channel"] == "inbox" and notification["state"] == "queued"
    assert notification["priority"] == "high"

    dispatch_jobs = [job for job in table_rows(harness, "jobs", owner_id=owner_id)
                     if job["job_type"] == "dispatch_notification"]
    assert len(dispatch_jobs) == 1
    assert dispatch_jobs[0]["payload_ref"] == f"notification:{notification['id']}"

    run_pending_jobs(harness, handlers)
    assert job_state(harness, dispatch_jobs[0]["id"])["state"] == "succeeded"
    assert table_rows(harness, "notifications", owner_id=owner_id)[0]["state"] == "delivered"

    # Within the cooldown the same failure is merged, not re-notified.
    repeat = handlers["health_check"]({"owner_id": owner_id, "payload_ref": "schedule:health_check:x"},
                                       FakeContext())
    assert repeat["notified"] is False
    assert len(table_rows(harness, "notifications", owner_id=owner_id)) == 1