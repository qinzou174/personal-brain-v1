"""Match-centered snippet windows for retrieval responses.

The index stores a fixed 300-char head excerpt (``display_excerpt``), so a
match landing deep inside a long document was invisible to consumers — the
knowledge base itself recorded this as「检索粒度的坑」. Hydration re-centers
the excerpt on the earliest query-token occurrence in the *source* text.
"""

from __future__ import annotations

import unicodedata

from personal_brain_infra.search.tokenization import tokenize

_RADIUS_BEFORE = 100
_RADIUS_AFTER = 220
_MAX_LEN = 340


def _clean(text: str) -> str:
    """Lone surrogates (upstream decoder artifacts) must never reach a JSON
    response with ensure_ascii=False — degrade them to U+FFFD instead."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return text.encode("utf-8", "surrogatepass").decode("utf-8", "replace")
    return text


def build_snippet(text: str, query: str) -> str | None:
    """Return a match-centered window of ``text`` or None when no query token
    occurs literally (pure-semantic hits keep their stored head excerpt).

    Malformed text degrades via U+FFFD replacement — snippet building must
    never break a search.
    """
    text = _clean(text or "")
    query = _clean(query or "")
    if not text or not query:
        return None
    normalized = unicodedata.normalize("NFKC", text).casefold()
    positions = []
    for token in tokenize(query):
        token = unicodedata.normalize("NFKC", token).casefold()
        if token:
            position = normalized.find(token)
            if position >= 0:
                positions.append(position)
    if not positions:
        return None
    start = max(0, min(positions) - _RADIUS_BEFORE)
    end = min(len(text), min(positions) + _RADIUS_AFTER)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    snippet = f"{prefix}{text[start:end]}{suffix}"
    return _clean(snippet if len(snippet) <= _MAX_LEN else f"{prefix}{text[start:start + _MAX_LEN - 2]}{suffix}")
