"""Contract: document length normalizes keyword scoring, never the fused score.

History: the O2 mitigation multiplied the fused RRF score by ``400/length``
(floor 0.1).  That inverted the ranking, because RRF scores live in a ~1/60 band
(0.009..0.033) while the penalty spans 10x.  Regression observed on
2026-09-24: a long archive that was the *only* keyword match (rank 1) and
semantic rank 1 for the query "壁纸" dropped out of the top 30 and answered
"库里没有壁纸内容".  Length bias really originates in single-list scoring
(jieba OR-matches accumulate in long documents -> ts_rank_cd favours them), so
length now acts inside the keyword list as match density and RRF stays the only
cross-list ranking authority.
"""
from __future__ import annotations

import inspect

from personal_brain_domain.retrieval.ranking import rrf_fuse
from personal_brain_infra.search.repository import PostgresSearchRepository


def _search_source() -> str:
    return inspect.getsource(PostgresSearchRepository.search)


def test_fused_score_is_not_scaled_by_document_length():
    """No length factor may multiply the fused RRF score (the O2 regression)."""
    src = _search_source()
    assert "_length_penalty" not in src
    assert "scores[item] *" not in src
    assert "*(-(scores[item] *" not in src
    assert "key=lambda item: (-scores[item]" in src


def test_keyword_list_orders_by_log_length_density():
    """ts_rank_cd's length bias is corrected where it originates."""
    src = _search_source()
    assert "keyword_density" in src
    assert "sa.func.ln(document_length)" in src
    assert "sa.func.greatest(sa.func.length(" in src
    assert 'sa.desc("keyword_density")' in src


def test_semantic_list_orders_by_distance_only():
    """Cosine distance is not length-normalized (embeddings are not keyword
    scoring; the observed archive ranking is already correct)."""
    src = _search_source()
    assert ".order_by(distance," in src


def test_top_of_both_lists_outranks_any_single_list_hit():
    """RRF property the penalty violated: appearing in both candidate lists at
    rank 1 must beat any record present in only one list."""
    fused = rrf_fuse(keyword_rank=["archive"], semantic_rank=["archive", "noise-1", "noise-2"])
    assert fused["archive"] > fused["noise-1"]
    assert max(fused, key=lambda key: (fused[key], key)) == "archive"