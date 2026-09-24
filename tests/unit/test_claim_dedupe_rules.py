"""D2: duplicate control is a deterministic rule, not a model judgement.

The thresholds are pinned here against real strings (measured with the retrieval
tokenizer), so a change in tokenization or thresholds cannot silently start
merging distinct claims.
"""

from __future__ import annotations

from personal_brain_worker.claim_dedupe import (
    claim_similarity, cosine_similarity, duplicate_kind, find_duplicate,
)


def test_identical_text_with_different_surface_form_is_a_duplicate():
    assert duplicate_kind("用户喜欢喝咖啡。", "用户喜欢喝咖啡") == "duplicate"
    assert duplicate_kind("倾向把项目、数据和记忆统一收拢到自有服务器体系。",
                          "倾向把项目、数据和记忆统一收拢到自有服务器体系") == "duplicate"


def test_near_identical_wordings_are_duplicates_above_the_merge_threshold():
    assert claim_similarity("倾向把项目、数据和记忆统一收拢到自有服务器体系。",
                            "倾向把项目、数据、记忆统一收拢到自有服务器体系。") >= 0.75
    assert duplicate_kind("倾向把项目、数据和记忆统一收拢到自有服务器体系。",
                          "倾向把项目、数据、记忆统一收拢到自有服务器体系。") == "duplicate"


def test_worded_differently_paraphrases_are_suspected_not_merged():
    # Only 0.52 token overlap: the worker must not merge these by itself.
    assert duplicate_kind(
        "倾向把项目、数据和记忆统一收拢到自有服务器体系。",
        "倾向把项目、数据与记忆统一收拢到自有服务器，而非散落在单一 AI 平台。",
    ) == "suspected"


def test_distinct_claims_stay_distinct():
    assert duplicate_kind("用户喜欢喝咖啡", "用户喜欢喝茶") == "distinct"
    assert duplicate_kind("善用 MCP 作为记忆库", "一边写一边存") == "distinct"
    assert claim_similarity("", "用户喜欢喝咖啡") == 0.0


def test_opposite_polarity_is_never_a_duplicate_even_when_text_overlaps_almost_fully():
    assert claim_similarity("倾向把项目、数据和记忆统一收拢到自有服务器体系。",
                            "不倾向把项目、数据和记忆统一收拢到自有服务器体系。") >= 0.75
    assert duplicate_kind("倾向把项目、数据和记忆统一收拢到自有服务器体系。",
                          "不倾向把项目、数据和记忆统一收拢到自有服务器体系。") == "distinct"


def test_find_duplicate_returns_the_closest_match():
    rows = [
        {"id": "far", "claim": "用户喜欢喝茶"},
        {"id": "near", "claim": "倾向把项目、数据、记忆统一收拢到自有服务器体系。"},
        {"id": "exact", "claim": "倾向把项目、数据和记忆统一收拢到自有服务器体系"},
    ]
    match = find_duplicate("倾向把项目、数据和记忆统一收拢到自有服务器体系。", rows)
    assert match is not None
    assert match[0]["id"] == "exact" and match[1] == "duplicate" and match[2] == 1.0
    assert find_duplicate("完全无关的一条陈述", rows) is None


def test_cosine_similarity_bounds():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine_similarity([], [1.0]) == 0.0
    assert round(cosine_similarity([0.9, 0.4359], [1.0, 0.0]), 4) == 0.9