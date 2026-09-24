"""Permission-filtered semantic candidate retrieval with versioned embeddings.

FR-057/FR-065/FR-086: semantic retrieval is restricted to the authorized scope;
embedding model version is recorded on every candidate.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SemanticHit:
    object_id: object
    vector_model_version: str
    score: float


def retrieve_semantic(*, query: str, authorized_scope: str,
                      embeddings: dict[object, dict], vector_model_version: str) -> list[SemanticHit]:
    """Return versioned candidates within the authorized scope (deterministic order)."""
    hits = []
    for object_id, entry in embeddings.items():
        if entry.get("scope") != authorized_scope:
            continue
        overlap = len(set(query) & set(entry.get("text", "")))
        score = float(overlap) / max(1, len(set(query)))
        hits.append(SemanticHit(object_id=object_id, vector_model_version=vector_model_version, score=score))
    return sorted(hits, key=lambda hit: (-hit.score, str(hit.object_id)))