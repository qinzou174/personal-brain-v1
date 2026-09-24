"""Locked Chinese/mixed-language tokenization for PostgreSQL simple FTS."""

from __future__ import annotations

import re
import unicodedata

import jieba

TOKENIZER_ID = "jieba-0.42.1-search-v1"
_LEXEME = re.compile(r"[\w./:@+-]+", re.UNICODE)


def tokenize(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    ordered: dict[str, None] = {}
    for token in jieba.cut_for_search(normalized, HMM=False):
        cleaned = token.strip()
        if cleaned and not cleaned.isspace():
            ordered.setdefault(cleaned, None)
    # Preserve unknown mixed-language terms and paths that jieba may split.
    for token in _LEXEME.findall(normalized):
        if token:
            ordered.setdefault(token, None)
    return tuple(ordered)


def fts_text(text: str) -> str:
    return " ".join(tokenize(text))


def fts_query_text(text: str) -> str:
    """Match any query segment when a phrase is embedded in a longer note."""
    return " OR ".join(tokenize(text))
