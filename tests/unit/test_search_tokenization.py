"""Locked Chinese/mixed-language tokenization for T179."""


def test_jieba_tokenization_is_deterministic_and_preserves_mixed_terms_and_paths():
    from personal_brain_infra.search.tokenization import TOKENIZER_ID, fts_text, tokenize

    first = tokenize("今天去了京都 PersonalBrain apps/server/main.py 未知词XYZ")
    second = tokenize("今天去了京都 PersonalBrain apps/server/main.py 未知词XYZ")
    assert first == second
    assert "京都" in first
    assert "personalbrain" in first
    assert "apps/server/main.py" in first
    assert TOKENIZER_ID == "jieba-0.42.1-search-v1"
    assert fts_text("京都") == "京都"


def test_chinese_query_uses_alternative_segments_for_embedded_phrase():
    from personal_brain_infra.search.tokenization import fts_query_text

    query = fts_query_text("青石计划")
    assert " OR " in query
    assert "青石" in query and "计划" in query
