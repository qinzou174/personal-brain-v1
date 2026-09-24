"""Ranking regression: length must not hide the only lexical match.

Chain-audit 2026-09-24 regression (real instance): the query "壁纸" had exactly
one keyword hit -- the 1663-character personal archive -- and that archive was
also semantic rank 1, yet it fell out of the top 30 and ``answer_brain``
concluded "库里没有壁纸内容", because the fused RRF score was multiplied by
``400/length`` (0.197 for that record).  This suite reproduces the shape of that
query against real PostgreSQL: one long document holding the query term,
surrounded by short lexically unrelated notes that are semantically closer.

Note: ``fts_text`` deduplicates tokens, so a long record only stays long when
its content is varied; both fixtures therefore assert their own premise length.
"""
from __future__ import annotations

import pytest

from activation_support import build_harness, insert_raw_input, seed_owner

VECTOR_VERSION = "test:length-normalization:1024"
DIMENSIONS = 1024
NOISE_NOTES = 30

HEADER = "真实档案-英语/图像审美/角色卡/壁纸\n九十、你手机壁纸喜欢有前后关系：封面 + 主壁纸，不要两张几乎一样。\n"


def _varied_body(tag: str, lines: int) -> str:
    return "".join(
        f"{tag}{index:03d}：黄昏室内书桌、猫、窗景与故事感构图。\n" for index in range(1, lines + 1)
    )


ARCHIVE = HEADER + _varied_body("壁纸审美素材", 100)
SPARSE = "壁纸\n" + _varied_body("摄影素材", 100)
DENSE = "壁纸：黄昏室内书桌"


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    h = build_harness(tmp_path_factory)
    yield h
    h.drop_schema()


def _axis_vector(axis: int) -> list[float]:
    vector = [0.0] * DIMENSIONS
    vector[axis] = 1.0
    return vector


def _index(repository, raw_id, text: str, *, axis: int) -> None:
    repository.index(
        target_type="raw_input", target_id=raw_id, authorized_scope="knowledge",
        sensitivity="normal", canonicality="canonical", freshness="fresh", text=text,
        source_links=[f"raw_input:{raw_id}"], vector_model_version=VECTOR_VERSION,
        embedding=_axis_vector(axis),
    )


def _repository(harness, owner_id):
    from personal_brain_infra.search.repository import PostgresSearchRepository

    return PostgresSearchRepository(
        harness.factory, harness.tables["search_index_entries"], owner_id=owner_id,
    )


def _indexed_length(text: str) -> int:
    from personal_brain_infra.search.tokenization import fts_text

    return len(fts_text(text))


def test_long_sole_lexical_match_survives_closer_short_notes(harness):
    # Premise: the record is long enough for the old 400/length penalty to bite.
    assert _indexed_length(ARCHIVE) > 800

    owner_id, client_id = seed_owner(harness)
    repository = _repository(harness, owner_id)
    archive_id = insert_raw_input(harness, owner_id, client_id, text=ARCHIVE)
    _index(repository, archive_id, ARCHIVE, axis=1)
    for noise in range(NOISE_NOTES):
        text = f"延迟探针写入{noise}号记录"
        noise_id = insert_raw_input(harness, owner_id, client_id, text=text)
        # Identical to the query vector: every noise note is semantically nearer
        # than the archive, which is what buried it in production.
        _index(repository, noise_id, text, axis=0)

    hits = repository.search(
        query="壁纸", authorized_scope="knowledge", sensitivity_ceiling="private",
        query_embedding=_axis_vector(0), vector_model_version=VECTOR_VERSION, limit=10,
    )

    assert hits, "the only lexical match must be retrievable"
    assert hits[0]["target_id"] == str(archive_id), (
        "RRF must rank the record that is the only keyword match above short "
        "notes that only win on semantic distance"
    )


def test_keyword_density_prefers_the_more_specific_document(harness):
    """Among equal ts_rank_cd hits, the denser (shorter) document ranks first."""
    assert _indexed_length(SPARSE) > 800 and _indexed_length(DENSE) < 100

    owner_id, client_id = seed_owner(harness)
    repository = _repository(harness, owner_id)
    for text in (DENSE, SPARSE):
        raw_id = insert_raw_input(harness, owner_id, client_id, text=text)
        _index(repository, raw_id, text, axis=0)
        if text == DENSE:
            dense_id = raw_id
        else:
            sparse_id = raw_id

    hits = repository.search(
        query="壁纸", authorized_scope="knowledge", sensitivity_ceiling="private",
        query_embedding=None, vector_model_version=None, limit=2,
    )

    assert [hit["target_id"] for hit in hits] == [str(dense_id), str(sparse_id)]