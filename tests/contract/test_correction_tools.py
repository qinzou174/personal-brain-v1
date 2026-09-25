"""Contract + store tests: correction/delete UX (003-correction-delete-ux).

Written data must stay correctable: update_note supersedes a note (R1),
delete_todo gives a low-risk record a direct terminal state (R2), and
correct_expense replaces an amount without adjustment double-counting (R3).
Every tombstone also removes the retrieval card in the same transaction, so
search stops serving stale content immediately.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from personal_brain_domain.common.errors import BrainError


def _harness(engine):
    from tests.integration.test_authoritative_store import _schema, _seed

    metadata = _schema(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    owner_id, client_id = _seed(factory, metadata)
    return factory, metadata, owner_id, client_id


def _store(factory, owner_id, client_id):
    from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore

    return AuthoritativeStore(factory, owner_id=owner_id, client_id=client_id)


def _seed_card(factory, metadata, owner_id, client_id, *, target_type, target_id, scope):
    """A fake retrieval card as the indexer would have projected it."""
    with factory.begin() as session:
        session.execute(metadata.tables["search_index_entries"].insert().values(
            id=uuid4(), owner_id=owner_id, target_type=target_type, target_id=target_id,
            authorized_scope=scope, sensitivity="normal", canonicality="canonical",
            valid_from=None, valid_to=None, freshness="fresh",
            searchable_text="seeded", search_document="seeded", embedding=None,
            vector_model_version=None, metadata_filters={}, indexed_at=None,
        ))


def _card_count(factory, metadata, owner_id, target_type, target_id):
    with factory() as session:
        return session.execute(sa.select(sa.func.count()).select_from(
            metadata.tables["search_index_entries"],
        ).where(
            metadata.tables["search_index_entries"].c.owner_id == owner_id,
            metadata.tables["search_index_entries"].c.target_type == target_type,
            metadata.tables["search_index_entries"].c.target_id == target_id,
        )).scalar_one()


# ---------------------------------------------------------------------------
# US1 — update_note: supersede semantics
# ---------------------------------------------------------------------------


def test_update_note_supersedes_old_note_and_removes_its_card(tmp_path):
    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'un.sqlite').as_posix()}")
    factory, metadata, owner_id, client_id = _harness(engine)
    store = _store(factory, owner_id, client_id)

    old = store.save_note(content="会议改到周四下午", requested_scope="knowledge", idempotency_key=uuid4())
    old_note_id = UUID(old["record_id"])
    _seed_card(factory, metadata, owner_id, client_id, target_type="raw_input",
               target_id=old_note_id, scope="knowledge")

    result = store.update_note(
        old_note_id=old_note_id, content="会议改到周五上午",
        requested_scope="knowledge", idempotency_key=uuid4(),
    )

    assert result["status"] == "accepted"
    assert result["record_id"] != old["record_id"]
    assert result["superseded_id"] == str(old_note_id)
    assert result["index_state"] == "pending"
    with factory() as session:
        raws = session.execute(sa.select(metadata.tables["raw_inputs"]).order_by(
            metadata.tables["raw_inputs"].c.created_at)).mappings().all()
    assert len(raws) == 2
    assert raws[0]["lifecycle_state"] == "deleted" and raws[0]["deleted_at"] is not None
    assert raws[1]["lifecycle_state"] == "active" and raws[1]["content_text"] == "会议改到周五上午"
    # the old card left the search view in the same transaction
    assert _card_count(factory, metadata, owner_id, "raw_input", old_note_id) == 0
    engine.dispose()


def test_update_note_rejects_unknown_or_gone_note(tmp_path):
    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'un404.sqlite').as_posix()}")
    factory, metadata, owner_id, client_id = _harness(engine)
    store = _store(factory, owner_id, client_id)

    with pytest.raises(BrainError) as missing:
        store.update_note(old_note_id=uuid4(), content="x", requested_scope="knowledge",
                          idempotency_key=uuid4())
    assert missing.value.code == "NOT_FOUND"

    old = store.save_note(content="旧笔记", requested_scope="knowledge", idempotency_key=uuid4())
    store.update_note(old_note_id=UUID(old["record_id"]), content="新笔记",
                      requested_scope="knowledge", idempotency_key=uuid4())
    with pytest.raises(BrainError) as gone:
        store.update_note(old_note_id=UUID(old["record_id"]), content="再改一次",
                          requested_scope="knowledge", idempotency_key=uuid4())
    assert gone.value.code == "NOT_FOUND", "a superseded note is honestly absent"
    engine.dispose()


def test_update_note_rejects_blank_content(tmp_path):
    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'unblank.sqlite').as_posix()}")
    factory, _metadata, owner_id, client_id = _harness(engine)
    store = _store(factory, owner_id, client_id)
    with pytest.raises(BrainError) as caught:
        store.update_note(old_note_id=uuid4(), content="   ", requested_scope="knowledge",
                          idempotency_key=uuid4())
    assert caught.value.code == "VALIDATION_FAILED"
    engine.dispose()


# ---------------------------------------------------------------------------
# US2 — delete_todo: direct terminal state
# ---------------------------------------------------------------------------


def test_delete_todo_tombstones_and_removes_card(tmp_path):
    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'dt.sqlite').as_posix()}")
    factory, metadata, owner_id, client_id = _harness(engine)
    store = _store(factory, owner_id, client_id)

    todo = store.add_todo(content="取快递", requested_scope="todo", idempotency_key=uuid4())
    todo_id = UUID(todo["todo_id"])
    _seed_card(factory, metadata, owner_id, client_id, target_type="todo",
               target_id=todo_id, scope="todo")

    result = store.delete_todo(todo_id=todo_id, expected_version=1, idempotency_key=uuid4())
    assert result["status"] == "accepted" and result["state"] == "deleted"
    assert store.list_todos() == []
    assert _card_count(factory, metadata, owner_id, "todo", todo_id) == 0
    with factory() as session:
        row = session.execute(sa.select(metadata.tables["todos"]).where(
            metadata.tables["todos"].c.id == todo_id)).mappings().one()
    assert row["lifecycle_state"] == "deleted" and row["deleted_at"] is not None
    engine.dispose()


def test_delete_todo_is_single_use_and_version_bound(tmp_path):
    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'dt2.sqlite').as_posix()}")
    factory, _metadata, owner_id, client_id = _harness(engine)
    store = _store(factory, owner_id, client_id)

    todo = store.add_todo(content="交报表", requested_scope="todo", idempotency_key=uuid4())
    todo_id = UUID(todo["todo_id"])

    with pytest.raises(BrainError) as stale:
        store.delete_todo(todo_id=todo_id, expected_version=2, idempotency_key=uuid4())
    assert stale.value.code == "VERSION_CONFLICT"

    store.delete_todo(todo_id=todo_id, expected_version=1, idempotency_key=uuid4())
    with pytest.raises(BrainError) as again:
        store.delete_todo(todo_id=todo_id, expected_version=2, idempotency_key=uuid4())
    assert again.value.code == "NOT_FOUND", "double delete is honestly absent"
    engine.dispose()


# ---------------------------------------------------------------------------
# US3 — correct_expense: replace, not adjust
# ---------------------------------------------------------------------------


def test_correct_expense_replaces_amount_and_summary_follows(tmp_path):
    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'ce.sqlite').as_posix()}")
    factory, metadata, owner_id, client_id = _harness(engine)
    store = _store(factory, owner_id, client_id)

    original = store.add_expense(
        amount="3.0000", currency="CNY", category="transport", description="地铁",
        occurred_timezone="Asia/Shanghai", requested_scope="finance",
        idempotency_key=uuid4(), source_text="地铁 3 CNY",
    )
    expense_id = UUID(original["expense_id"])
    _seed_card(factory, metadata, owner_id, client_id, target_type="raw_input",
               target_id=UUID(original["source_id"]), scope="finance")

    result = store.correct_expense(
        expense_id=expense_id, new_amount=Decimal("7"), requested_scope="finance",
        idempotency_key=uuid4(),
    )

    assert result["status"] == "accepted"
    assert result["corrected_from"] == str(expense_id)
    assert result["expense_id"] != str(expense_id)
    assert result["index_state"] == "pending"
    summary = store.get_expense_summary()
    assert summary["totals"] == [{"currency": "CNY", "amount": "7.0000", "record_count": 1}]
    rows = store.list_expenses()
    assert len(rows) == 1 and rows[0]["description"] == "更正：地铁"
    with factory() as session:
        new_row = session.execute(sa.select(metadata.tables["expenses"]).where(
            metadata.tables["expenses"].c.id == UUID(result["expense_id"]))).mappings().one()
        old_row = session.execute(sa.select(metadata.tables["expenses"]).where(
            metadata.tables["expenses"].c.id == expense_id)).mappings().one()
    assert int(new_row["version"]) == 2
    assert old_row["lifecycle_state"] == "deleted"
    # the old expense's raw source and its card left the search view
    assert _card_count(factory, metadata, owner_id, "raw_input", UUID(original["source_id"])) == 0
    engine.dispose()


def test_correct_expense_rejects_missing_expense_and_bad_amount(tmp_path):
    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'ce2.sqlite').as_posix()}")
    factory, _metadata, owner_id, client_id = _harness(engine)
    store = _store(factory, owner_id, client_id)

    with pytest.raises(BrainError) as missing:
        store.correct_expense(expense_id=uuid4(), new_amount=Decimal("1"),
                              requested_scope="finance", idempotency_key=uuid4())
    assert missing.value.code == "NOT_FOUND"

    original = store.add_expense(
        amount="10.0000", currency="CNY", category="food", description="午饭",
        occurred_timezone="Asia/Shanghai", requested_scope="finance",
        idempotency_key=uuid4(), source_text="午饭 10 CNY",
    )
    with pytest.raises(BrainError) as invalid:
        store.correct_expense(expense_id=UUID(original["expense_id"]), new_amount=Decimal("-5"),
                              requested_scope="finance", idempotency_key=uuid4())
    assert invalid.value.code == "VALIDATION_FAILED", "in-band validation, not a transport error"
    engine.dispose()


# ---------------------------------------------------------------------------
# US4 — index_state on card-producing writes
# ---------------------------------------------------------------------------


def test_card_producing_writes_report_index_pending(tmp_path):
    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'isp.sqlite').as_posix()}")
    factory, _metadata, owner_id, client_id = _harness(engine)
    store = _store(factory, owner_id, client_id)

    assert store.save_note(content="a note", requested_scope="knowledge",
                           idempotency_key=uuid4())["index_state"] == "pending"
    assert store.add_todo(content="a todo", requested_scope="todo",
                          idempotency_key=uuid4())["index_state"] == "pending"
    assert store.add_expense(
        amount="1.0000", currency="CNY", category="food", description="x",
        occurred_timezone="UTC", requested_scope="finance",
        idempotency_key=uuid4(), source_text="x 1 CNY",
    )["index_state"] == "pending"
    engine.dispose()


# ---------------------------------------------------------------------------
# US6 + US10 — propose_self_claim: real-time conflict hint + A-class semantics
# ---------------------------------------------------------------------------


def test_propose_self_claim_warns_on_same_topic_opposite_polarity(tmp_path):
    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'cw.sqlite').as_posix()}")
    factory, _metadata, owner_id, client_id = _harness(engine)
    store = _store(factory, owner_id, client_id)

    first = store.propose_self_claim(category="preference", claim_text="我喜欢喝茶",
                                     policy_class="A", requested_scope="self",
                                     idempotency_key=uuid4())

    view = store.get_self_context(categories=["preference"])
    mine = [c for c in view["claims"] if c["claim_id"] == first["claim_id"]]
    assert mine and mine[0]["lifecycle_state"] == "active", "A-class takes effect immediately"

    contradicting = store.propose_self_claim(category="preference", claim_text="我不喜欢喝茶",
                                             policy_class="B", requested_scope="self",
                                             idempotency_key=uuid4())
    warning = contradicting.get("conflict_warning")
    assert warning is not None
    assert warning["claim_id"] == first["claim_id"]
    assert "喝茶" in warning["claim"]

    unrelated = store.propose_self_claim(category="value", claim_text="证据优先",
                                         policy_class="B", requested_scope="self",
                                         idempotency_key=uuid4())
    assert "conflict_warning" not in unrelated, "no polarity conflict, no hint"
    engine.dispose()


def test_b_and_c_claims_stay_candidates(tmp_path):
    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'bc.sqlite').as_posix()}")
    factory, _metadata, owner_id, client_id = _harness(engine)
    store = _store(factory, owner_id, client_id)

    b = store.propose_self_claim(category="habit", claim_text="晨跑", policy_class="B",
                                 requested_scope="self", idempotency_key=uuid4())
    c = store.propose_self_claim(category="aesthetic", claim_text="喜欢极简",
                                 policy_class="C", requested_scope="self",
                                 idempotency_key=uuid4())
    view = store.get_self_context()
    states = {item["claim_id"]: item["lifecycle_state"] for item in view["claims"]}
    assert states[b["claim_id"]] == "candidate"
    assert states[c["claim_id"]] == "candidate"
    engine.dispose()


# ---------------------------------------------------------------------------
# race convergence: absent source => no card (indexer last-writer enforcement)
# ---------------------------------------------------------------------------


def test_index_job_settles_source_gone_and_drops_surviving_card(tmp_path):
    """A late index job that read the source before the tombstone committed can
    insert its card after the tombstone's card-DELETE matched 0 rows. The
    indexer must enforce "absent source => no card" at the last writer."""
    from personal_brain_infra.search.indexer import SearchIndexer

    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'race.sqlite').as_posix()}")
    factory, metadata, owner_id, client_id = _harness(engine)
    store = _store(factory, owner_id, client_id)

    note = store.save_note(content="竞态演练笔记", requested_scope="knowledge", idempotency_key=uuid4())
    note_id = UUID(note["record_id"])
    _seed_card(factory, metadata, owner_id, client_id, target_type="raw_input",
               target_id=note_id, scope="knowledge")
    # the source is tombstoned (as update_note would) but the card survives —
    # exactly the post-race state observed in production verification
    with factory.begin() as session:
        session.execute(metadata.tables["raw_inputs"].update().where(
            metadata.tables["raw_inputs"].c.id == note_id,
        ).values(lifecycle_state="deleted", deleted_at=None))

    indexer = SearchIndexer(factory, metadata.tables)
    result = indexer.handle({"payload_ref": f"raw_input:{note_id}", "owner_id": str(owner_id),
                             "job_type": "index_raw_input"})

    assert result["skipped"] == "source_gone" and result["indexed"] is False
    assert _card_count(factory, metadata, owner_id, "raw_input", note_id) == 0, \
        "the surviving card must be dropped by the indexer itself"
    engine.dispose()


def test_update_note_queues_trailing_index_job_for_old_note(tmp_path):
    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'trailing.sqlite').as_posix()}")
    factory, metadata, owner_id, client_id = _harness(engine)
    store = _store(factory, owner_id, client_id)

    old = store.save_note(content="旧的", requested_scope="knowledge", idempotency_key=uuid4())
    old_id = UUID(old["record_id"])
    store.update_note(old_note_id=old_id, content="新的", requested_scope="knowledge",
                      idempotency_key=uuid4())
    with factory() as session:
        pending = session.execute(sa.select(metadata.tables["jobs"].c.job_type).where(
            metadata.tables["jobs"].c.job_type == "index_raw_input",
            metadata.tables["jobs"].c.payload_ref == f"raw_input:{old_id}",
            metadata.tables["jobs"].c.state == "queued",
        )).scalars().all()
    # two queued jobs reference the tombstoned source: the original save_note
    # index job plus the trailing convergence job queued by update_note
    assert len(pending) == 2 and set(pending) == {"index_raw_input"}, \
        "a trailing job for the tombstoned source converges the card race"
    engine.dispose()


def test_extract_job_skips_tombstoned_source_without_dead_letter(tmp_path):
    from apps.worker.personal_brain_worker.extraction import make_extract_handler

    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'extskip.sqlite').as_posix()}")
    factory, metadata, owner_id, client_id = _harness(engine)
    store = _store(factory, owner_id, client_id)

    note = store.save_note(content="将被更正的笔记", requested_scope="knowledge", idempotency_key=uuid4())
    note_id = UUID(note["record_id"])
    store.update_note(old_note_id=note_id, content="更正后的笔记", requested_scope="knowledge",
                      idempotency_key=uuid4())

    # the handler unpacks the evidence table at entry; the source_gone branch
    # returns before touching it, so a stub table object suffices on sqlite
    evidence_stub = sa.Table("evidence", sa.MetaData(), sa.Column("id", sa.Uuid, primary_key=True))
    tables = {**metadata.tables, "evidence": evidence_stub}
    handler = make_extract_handler(factory, tables, storage=None, gateway=None)
    result = handler({"payload_ref": f"raw_input:{note_id}", "owner_id": str(owner_id),
                      "job_type": "extract_raw_input"}, context=None)
    assert result == {"extracted": 0, "dropped": 0, "skipped": "source_gone"}
    engine.dispose()


# ---------------------------------------------------------------------------
# US5 — time-range search plumbing (service-level normalization)
# ---------------------------------------------------------------------------


def _search_service(store):
    from types import SimpleNamespace
    from uuid import uuid4 as _uuid4
    from personal_brain_server.api.authorized_tools import AuthorizedToolService

    class Ok:
        def authenticate(self, credential):
            return SimpleNamespace(owner_id=_uuid4(), client_id=_uuid4(), authenticated_epoch=1)

        def authorize(self, context, **kwargs):
            return True

    captured: dict = {}

    class Repo:
        def search(self, **kwargs):
            captured.update(kwargs)
            return []

    service = AuthorizedToolService(
        Ok(), lambda **_kw: store, search_factory=lambda **_kw: Repo(),
    )
    return service, captured


def test_search_time_bounds_normalize_and_invalid_bounds_rejected():
    service, captured = _search_service(store=None)
    service.search_brain(credential="opaque", query="上周记了什么", requested_scope="knowledge",
                         time_from="2026-09-01", time_to="2026-09-15")
    assert captured["time_from"] == "2026-09-01T00:00:00"
    assert captured["time_to"] == "2026-09-15T23:59:59.999999", "a bare date covers the whole day"

    with pytest.raises(BrainError) as caught:
        service.search_brain(credential="opaque", query="x", requested_scope="knowledge",
                             time_from="not-a-date")
    assert caught.value.code == "VALIDATION_FAILED"


# ---------------------------------------------------------------------------
# service-level authorization + validation contracts
# ---------------------------------------------------------------------------


class RecordingAuthority:
    def __init__(self, *, allowed: set[str] | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.allowed = allowed
        from uuid import uuid4 as _uuid4
        self.owner_id, self.client_id = _uuid4(), _uuid4()

    def authenticate(self, credential: str):
        from types import SimpleNamespace
        return SimpleNamespace(owner_id=self.owner_id, client_id=self.client_id,
                               authenticated_epoch=1)

    def authorize(self, context, *, tool: str, scope: str, sensitivity: str, risk="ordinary", now=None):
        self.calls.append((tool, scope))
        if self.allowed is not None and tool not in self.allowed:
            raise BrainError("SCOPE_DENIED")
        return True


class PassthroughStore:
    def __init__(self):
        self.calls: list[tuple] = []

    def update_note(self, **kwargs):
        self.calls.append(("update_note", kwargs))
        return {"status": "accepted"}

    def delete_todo(self, **kwargs):
        self.calls.append(("delete_todo", kwargs))
        return {"status": "accepted"}

    def correct_expense(self, **kwargs):
        self.calls.append(("correct_expense", kwargs))
        return {"status": "accepted"}


def _correction_service(authority, store):
    from personal_brain_server.api.authorized_tools import AuthorizedToolService

    return AuthorizedToolService(authority, lambda **_kw: store, search_factory=lambda **_kw: None)


def test_correction_tools_authorize_their_domain_write():
    authority = RecordingAuthority()
    store = PassthroughStore()
    service = _correction_service(authority, store)

    service.update_note(credential="opaque", old_note_id=uuid4(), content="x",
                        requested_scope="knowledge", idempotency_key=uuid4())
    service.delete_todo(credential="opaque", todo_id=uuid4(), expected_version=1,
                        idempotency_key=uuid4())
    service.correct_expense(credential="opaque", expense_id=uuid4(), new_amount="9.90",
                            requested_scope="finance", idempotency_key=uuid4())

    assert [call[0] for call in authority.calls] == [
        "knowledge.write", "knowledge.write",  # pre + post recheck
        "todo.write", "todo.write",
        "finance.write", "finance.write",
    ]
    assert [call[0] for call in store.calls] == ["update_note", "delete_todo", "correct_expense"]
    assert store.calls[2][1]["new_amount"] == Decimal("9.90")


def test_correction_tools_denied_without_their_write_grant():
    store = PassthroughStore()
    service = _correction_service(RecordingAuthority(allowed={"knowledge.read"}), store)

    with pytest.raises(BrainError) as caught:
        service.update_note(credential="opaque", old_note_id=uuid4(), content="x",
                            requested_scope="knowledge", idempotency_key=uuid4())
    assert caught.value.code == "SCOPE_DENIED"

    with pytest.raises(BrainError) as todo_denied:
        service.delete_todo(credential="opaque", todo_id=uuid4(), expected_version=1,
                            idempotency_key=uuid4())
    assert todo_denied.value.code == "SCOPE_DENIED"

    with pytest.raises(BrainError) as finance_denied:
        service.correct_expense(credential="opaque", expense_id=uuid4(), new_amount="1",
                                requested_scope="finance", idempotency_key=uuid4())
    assert finance_denied.value.code == "SCOPE_DENIED"


def test_correct_expense_non_numeric_amount_is_validation_failed():
    service = _correction_service(RecordingAuthority(), PassthroughStore())
    with pytest.raises(BrainError) as caught:
        service.correct_expense(credential="opaque", expense_id=uuid4(), new_amount="abc",
                                requested_scope="finance", idempotency_key=uuid4())
    assert caught.value.code == "VALIDATION_FAILED"


# ---------------------------------------------------------------------------
# router vocabulary (US8)
# ---------------------------------------------------------------------------


def test_router_matrix_covers_natural_phrasings():
    from personal_brain_domain.retrieval.router import classify_intent

    todo_queries = ["我今天要做的事有哪些", "待办事项", "该办的事", "有什么要办的", "任务清单", "todo"]
    expense_queries = ["这个月买了什么", "最近花了多少", "花销汇总", "日常开支", "总支出多少", "打车花了多少钱"]
    for query in todo_queries:
        assert classify_intent(query) == "todo_list", query
    for query in expense_queries:
        assert classify_intent(query) == "expense_total", query
    # non-money contexts must not fall into the exact finance path (ER-04)
    assert classify_intent("帮他花了三天时间整理文档") == "fuzzy_idea"


# ---------------------------------------------------------------------------
# shared polarity rule: worker and domain can never disagree
# ---------------------------------------------------------------------------


def test_worker_and_domain_polarity_rules_are_the_same_object():
    from personal_brain_domain.memory import polarity as domain_polarity
    from personal_brain_worker import evolution

    assert evolution.is_negative is domain_polarity.is_negative
    assert evolution.topic_key is domain_polarity.topic_key
    assert domain_polarity.is_negative("不再熬夜") is True
    assert domain_polarity.is_negative("早睡早起") is False
