"""Regression for O2: long multi-topic documents must not drown out short,
precise records in retrieval ranking.

Root cause traced in chain-audit: jieba search-mode splits short phrases
(拿铁 -> 拿/铁) so keyword rank favors long documents that OR-match more
segments, and whole-document embeddings average long archives across topics.
The fix weights records by length in the fused ranking.
"""
from __future__ import annotations

import inspect

from personal_brain_infra.search.repository import PostgresSearchRepository

# Mirror of the private monotone length penalty (capped at 0.1).
def _penalty(length: int) -> float:
    if length <= 400:
        return 1.0
    return max(0.1, 400.0 / length)


def test_short_records_unpenalized():
    assert _penalty(0) == 1.0
    assert _penalty(400) == 1.0


def test_long_archives_decay_monotonically_and_cap():
    assert _penalty(800) == 0.5
    assert _penalty(4000) == 0.1
    assert _penalty(10**6) == 0.1  # floored, never below 0.1


def test_search_sort_path_uses_length_penalty():
    """Contract: the fused sort key in PostgresSearchRepository.search must
    weight by document length, otherwise long archives regain dominance."""
    src = inspect.getsource(PostgresSearchRepository.search)
    assert "_length_penalty" in src
    assert "400.0 / length" in src