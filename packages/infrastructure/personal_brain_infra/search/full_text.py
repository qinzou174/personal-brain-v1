"""Permission-filtered full-text candidate retrieval.

FR-057/FR-067: full-text candidates are retrieved only inside the authorized
scope; denied content never enters the candidate set.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FtsHit:
    object_id: object
    text: str
    scope: str


def retrieve_full_text(*, query: str, authorized_scope: str, corpus: dict[object, dict]) -> list[FtsHit]:
    """Match query tokens only against entries whose scope equals the authorized one."""
    tokens = {token for token in query.split() if token}
    hits = []
    for object_id, entry in corpus.items():
        if entry.get("scope") != authorized_scope:
            continue  # denied content never enters the candidate set
        text = entry.get("text", "")
        if tokens and any(token in text for token in tokens):
            hits.append(FtsHit(object_id=object_id, text=text[:200], scope=authorized_scope))
    return hits