"""Chunked semantic indexing: long documents must be semantically retrievable.

Regression for the RRF single-list drowning (2026-09-26, real instance): a
15.4KB handoff document was lexical rank 1 for its own token yet absent from
the semantic top-50, because a whole-document embedding averages every topic.
With one whole-vector competitor field, the document's fused score (~1/71) can
never beat cards that hit both lists (~2/61).

This suite reproduces that shape against real PostgreSQL with deterministic
axis vectors, then asserts the chunked path fixes it:

- whole-vector path: the long doc is lexical rank ~11 (low density) and
  semantically absent (diluted vector) -> drowned by 10 dual-list notes;
- chunked path: the section that actually matches the query enters the
  semantic list at rank 1 (max chunk score) -> the doc reaches the top 10.

Also locks the chunk lifecycle: re-index replacement, CASCADE on card delete,
and scope/time filters inherited from the parent card.
"""
from __future__ import annotations

import sqlalchemy as sa
import pytest

from activation_support import build_harness, insert_raw_input, seed_owner

VECTOR_VERSION = "test:chunked-semantic:1024"
DIMENSIONS = 1024
NOISE_NOTES = 60
DUAL_NOTES = 10  # notes 0..9 also contain the query token (dual-list competitors)
TOKEN = "锚点信号"

HEADER = "长文归档-部署与检索排查手记\n"


_counter = {"line": 0}


def _varied_body(tag: str, lines: int) -> str:
    body = []
    for _ in range(lines):
        _counter["line"] += 1
        body.append(f"{tag}{_counter['line']:03d}：黄昏室内书桌、猫、窗景与故事感构图。")
    return "\n".join(body)


# Long enough to chunk (>=2000 raw chars); the token sits in exactly one
# paragraph, i.e. <10% of the document.
LONG_DOC = (
    HEADER
    + "\n\n".join(_varied_body("部署手记", 4) for _ in range(22))
    + f"\n\n排查结论：{TOKEN}是那次会话生命周期问题的稳定复现词。\n\n"
    + "\n\n".join(_varied_body("收尾手记", 4) for _ in range(8))
)


def _unit(axis: int) -> list[float]:
    vector = [0.0] * DIMENSIONS
    vector[axis] = 1.0
    return vector


def _noise_vector(index: int) -> list[float]:
    # Strictly increasing cosine distance from the query (e0): rank order of
    # the noise notes is deterministic, no UUID-order flakiness.
    vector = [0.0] * DIMENSIONS
    vector[0] = 1.0
    vector[1] = 0.1 * index
    return vector


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    h = build_harness(tmp_path_factory)
    yield h
    h.drop_schema()


def _repository(harness, owner_id):
    from personal_brain_infra.search.repository import PostgresSearchRepository

    return PostgresSearchRepository(
        harness.factory, harness.tables["search_index_entries"], owner_id=owner_id,
        chunk_table=harness.tables.get("search_index_chunks"),
    )


def _seed_noise(harness, owner_id, client_id, repository) -> None:
    for index in range(NOISE_NOTES):
        text = f"延迟探针{index}号记录"
        if index < DUAL_NOTES:
            text += f"，{TOKEN}出现在短讯里"
        noise_id = insert_raw_input(harness, owner_id, client_id, text=text)
        repository.index(
            target_type="raw_input", target_id=noise_id, authorized_scope="knowledge",
            sensitivity="normal", canonicality="canonical", freshness="fresh", text=text,
            source_links=[f"raw_input:{noise_id}"], vector_model_version=VECTOR_VERSION,
            embedding=_noise_vector(index),
        )


def _chunk_vectors(harness, text: str) -> list[tuple[str, list[float]]]:
    from personal_brain_infra.search.chunking import split_chunks

    return [
        (piece, _unit(0) if TOKEN in piece else _unit(1))
        for piece in split_chunks(text)
    ]


def test_premise_long_doc_chunks_and_stays_long_under_fts(harness):
    from personal_brain_infra.search.chunking import split_chunks
    from personal_brain_infra.search.tokenization import fts_text

    assert len(LONG_DOC) >= 2000
    chunks = split_chunks(LONG_DOC)
    assert len(chunks) >= 2
    assert any(TOKEN in piece for piece in chunks)
    # fts_text deduplicates tokens (#14): length must come from varied content.
    assert len(fts_text(LONG_DOC)) > 800


def test_whole_vector_long_doc_is_drowned_by_dual_list_notes(harness):
    owner_id, client_id = seed_owner(harness)
    repository = _repository(harness, owner_id)
    _seed_noise(harness, owner_id, client_id, repository)
    doc_id = insert_raw_input(harness, owner_id, client_id, text=LONG_DOC)
    # The pre-fix shape: one whole-document vector, diluted to (nearly) pure
    # noise-axis, so the doc is semantically absent from the top-50.
    repository.index(
        target_type="raw_input", target_id=doc_id, authorized_scope="knowledge",
        sensitivity="normal", canonicality="canonical", freshness="fresh", text=LONG_DOC,
        source_links=[f"raw_input:{doc_id}"], vector_model_version=VECTOR_VERSION,
        embedding=_unit(1),
    )

    hits = repository.search(
        query=TOKEN, authorized_scope="knowledge", sensitivity_ceiling="private",
        query_embedding=_unit(0), vector_model_version=VECTOR_VERSION, limit=10,
    )
    top_ids = [hit["target_id"] for hit in hits]
    assert len(top_ids) == 10
    assert str(doc_id) not in top_ids, (
        "pre-fix shape must reproduce: a lexical-only long doc (diluted vector) "
        "is drowned by short dual-list notes"
    )


def test_chunked_long_doc_reaches_the_top(harness):
    owner_id, client_id = seed_owner(harness)
    repository = _repository(harness, owner_id)
    _seed_noise(harness, owner_id, client_id, repository)
    doc_id = insert_raw_input(harness, owner_id, client_id, text=LONG_DOC)
    repository.index(
        target_type="raw_input", target_id=doc_id, authorized_scope="knowledge",
        sensitivity="normal", canonicality="canonical", freshness="fresh", text=LONG_DOC,
        source_links=[f"raw_input:{doc_id}"], vector_model_version=VECTOR_VERSION,
        chunks=_chunk_vectors(harness, LONG_DOC),
    )

    hits = repository.search(
        query=TOKEN, authorized_scope="knowledge", sensitivity_ceiling="private",
        query_embedding=_unit(0), vector_model_version=VECTOR_VERSION, limit=10,
    )
    top_ids = [hit["target_id"] for hit in hits]
    assert str(doc_id) in top_ids, (
        "the matching section's own vector must carry the long doc into the "
        "semantic list (max chunk score) so RRF no longer drowns it"
    )

    # The parent card must be chunk-only: no diluted whole-doc vector competes.
    with harness.factory() as session:
        row = session.execute(sa.select(
            harness.tables["search_index_entries"].c.embedding,
        ).where(
            harness.tables["search_index_entries"].c.target_id == doc_id,
        )).mappings().one()
        assert row["embedding"] is None
        stored = session.execute(sa.select(
            sa.func.count(),
        ).select_from(harness.tables["search_index_chunks"])).scalar_one()
    assert stored == len(_chunk_vectors(harness, LONG_DOC))


def _chunk_count_for(harness, **entry_filters) -> int:
    """Chunk rows whose parent card matches the given entry filters."""
    entries = harness.tables["search_index_entries"]
    chunks = harness.tables["search_index_chunks"]
    statement = sa.select(sa.func.count()).select_from(chunks).join(
        entries, chunks.c.entry_id == entries.c.id,
    )
    for column, value in entry_filters.items():
        statement = statement.where(entries.c[column] == value)
    with harness.factory() as session:
        return session.execute(statement).scalar_one()


def test_short_doc_behavior_is_unchanged(harness):
    owner_id, client_id = seed_owner(harness)
    repository = _repository(harness, owner_id)
    text = "短路笔记：只有一行"
    note_id = insert_raw_input(harness, owner_id, client_id, text=text)
    repository.index(
        target_type="raw_input", target_id=note_id, authorized_scope="knowledge",
        sensitivity="normal", canonicality="canonical", freshness="fresh", text=text,
        source_links=[f"raw_input:{note_id}"], vector_model_version=VECTOR_VERSION,
        embedding=_unit(0),
    )

    hits = repository.search(
        query="短路笔记", authorized_scope="knowledge", sensitivity_ceiling="private",
        query_embedding=_unit(0), vector_model_version=VECTOR_VERSION, limit=5,
    )
    assert hits[0]["target_id"] == str(note_id)
    assert _chunk_count_for(harness, target_id=note_id) == 0, (
        "the short path must not create chunk rows"
    )


def test_reindex_replaces_chunks_without_orphans(harness):
    owner_id, client_id = seed_owner(harness)
    repository = _repository(harness, owner_id)
    doc_id = insert_raw_input(harness, owner_id, client_id, text=LONG_DOC)
    repository.index(
        target_type="raw_input", target_id=doc_id, authorized_scope="knowledge",
        sensitivity="normal", canonicality="canonical", freshness="fresh", text=LONG_DOC,
        source_links=[], vector_model_version=VECTOR_VERSION,
        chunks=_chunk_vectors(harness, LONG_DOC),
    )
    # Shorter rewrite -> fewer chunks; the old card row (and its chunks) dies.
    shorter = LONG_DOC[: len(LONG_DOC) // 2]
    repository.index(
        target_type="raw_input", target_id=doc_id, authorized_scope="knowledge",
        sensitivity="normal", canonicality="canonical", freshness="fresh", text=shorter,
        source_links=[], vector_model_version=VECTOR_VERSION,
        chunks=_chunk_vectors(harness, shorter),
    )

    with harness.factory() as session:
        entries = session.execute(sa.select(sa.func.count()).select_from(
            harness.tables["search_index_entries"],
        ).where(
            harness.tables["search_index_entries"].c.target_id == doc_id,
            harness.tables["search_index_entries"].c.vector_model_version == VECTOR_VERSION,
        )).scalar_one()
    assert entries == 1
    assert _chunk_count_for(harness, target_id=doc_id) == len(_chunk_vectors(harness, shorter))


def test_chunks_cascade_with_the_parent_card(harness):
    owner_id, client_id = seed_owner(harness)
    repository = _repository(harness, owner_id)
    doc_id = insert_raw_input(harness, owner_id, client_id, text=LONG_DOC)
    repository.index(
        target_type="raw_input", target_id=doc_id, authorized_scope="knowledge",
        sensitivity="normal", canonicality="canonical", freshness="fresh", text=LONG_DOC,
        source_links=[], vector_model_version=VECTOR_VERSION,
        chunks=_chunk_vectors(harness, LONG_DOC),
    )
    entries = harness.tables["search_index_entries"]
    chunks = harness.tables["search_index_chunks"]
    with harness.factory() as session:
        entry_ids = session.execute(sa.select(entries.c.id).where(
            entries.c.target_id == doc_id,
        )).scalars().all()
        assert entry_ids, "the card must exist before the tombstone"
        before = session.execute(sa.select(sa.func.count()).select_from(chunks).where(
            chunks.c.entry_id.in_(entry_ids),
        )).scalar_one()
        assert before > 0
        session.execute(sa.delete(entries).where(entries.c.target_id == doc_id))
        after = session.execute(sa.select(sa.func.count()).select_from(chunks).where(
            chunks.c.entry_id.in_(entry_ids),
        )).scalar_one()
    assert after == 0, "tombstoning the card must cascade-delete its chunks"


def test_scope_and_time_filters_inherit_from_parent_card(harness):
    owner_id, client_id = seed_owner(harness)
    repository = _repository(harness, owner_id)
    doc_id = insert_raw_input(harness, owner_id, client_id, text=LONG_DOC)
    repository.index(
        target_type="raw_input", target_id=doc_id, authorized_scope="knowledge",
        sensitivity="normal", canonicality="canonical", freshness="fresh", text=LONG_DOC,
        source_links=[], vector_model_version=VECTOR_VERSION,
        chunks=_chunk_vectors(harness, LONG_DOC),
        content_time="2026-01-15T00:00:00+00:00",
    )

    def _hit_ids(**kwargs):
        return [hit["target_id"] for hit in repository.search(
            query=TOKEN, authorized_scope="knowledge", sensitivity_ceiling="private",
            query_embedding=_unit(0), vector_model_version=VECTOR_VERSION, limit=5, **kwargs,
        )]

    assert str(doc_id) in _hit_ids(time_from="2026-01-01", time_to="2026-02-01")
    assert str(doc_id) not in _hit_ids(time_from="2026-06-01")
    # A different scope must not see the chunk hit either.
    other = repository.search(
        query=TOKEN, authorized_scope="finance", sensitivity_ceiling="private",
        query_embedding=_unit(0), vector_model_version=VECTOR_VERSION, limit=5,
    )
    assert other == []


class _FakeEmbedder:
    """Deterministic single-text embedder; no embed_many (exercises the
    per-chunk fallback loop in the indexer)."""

    model_version = "fake:chunk-embedder:4"

    def __init__(self, reject: bool = False) -> None:
        self.calls = 0
        self._reject = reject

    def embed(self, text: str) -> list[float]:
        self.calls += 1
        if self._reject:
            from personal_brain_domain.common.errors import BrainError
            raise BrainError("SECRET_REJECTED")
        return [float(len(text) % 5 + 1), 0.0, 0.0, 0.0]


def _handle_index(harness, owner_id, target_id, embedder) -> dict:
    from personal_brain_infra.search.indexer import SearchIndexer

    indexer = SearchIndexer(harness.factory, harness.tables, embedder=embedder)
    return indexer.handle({"payload_ref": f"raw_input:{target_id}", "owner_id": str(owner_id)})


def test_indexer_chunks_long_documents(harness):
    from personal_brain_infra.search.chunking import split_chunks

    owner_id, client_id = seed_owner(harness)
    doc_id = insert_raw_input(harness, owner_id, client_id, text=LONG_DOC)
    embedder = _FakeEmbedder()
    result = _handle_index(harness, owner_id, doc_id, embedder)

    assert result["indexed"] is True
    assert result["chunk_count"] == len(split_chunks(LONG_DOC)) >= 2
    with harness.factory() as session:
        row = session.execute(sa.select(
            harness.tables["search_index_entries"].c.embedding,
            harness.tables["search_index_entries"].c.vector_model_version,
        ).where(harness.tables["search_index_entries"].c.target_id == doc_id)).mappings().one()
        assert row["embedding"] is None, "chunked cards carry no whole-doc vector"
        assert row["vector_model_version"] == embedder.model_version
    assert _chunk_count_for(harness, target_id=doc_id) == result["chunk_count"]
    assert embedder.calls == len(split_chunks(LONG_DOC))


def test_indexer_short_document_keeps_whole_vector(harness):
    owner_id, client_id = seed_owner(harness)
    text = "短文：不走分块路径"
    note_id = insert_raw_input(harness, owner_id, client_id, text=text)
    embedder = _FakeEmbedder()
    result = _handle_index(harness, owner_id, note_id, embedder)

    assert result["indexed"] is True
    assert "chunk_count" not in result
    with harness.factory() as session:
        row = session.execute(sa.select(
            harness.tables["search_index_entries"].c.embedding,
        ).where(harness.tables["search_index_entries"].c.target_id == note_id)).mappings().one()
        assert row["embedding"] is not None
    assert _chunk_count_for(harness, target_id=note_id) == 0
    assert embedder.calls == 1


def test_indexer_secret_long_doc_degrades_to_keyword_only(harness):
    owner_id, client_id = seed_owner(harness)
    doc_id = insert_raw_input(harness, owner_id, client_id, text=LONG_DOC)
    embedder = _FakeEmbedder(reject=True)
    result = _handle_index(harness, owner_id, doc_id, embedder)

    assert result["indexed"] is True
    assert result["warnings"] == ["secret_like_semantic_skipped"]
    assert "chunk_count" not in result
    with harness.factory() as session:
        row = session.execute(sa.select(
            harness.tables["search_index_entries"].c.embedding,
            harness.tables["search_index_entries"].c.vector_model_version,
        ).where(harness.tables["search_index_entries"].c.target_id == doc_id)).mappings().one()
        assert row["embedding"] is None
        assert row["vector_model_version"] is None
    assert _chunk_count_for(harness, target_id=doc_id) == 0
