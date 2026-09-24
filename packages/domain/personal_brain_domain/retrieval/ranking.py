"""Rank normalization: hard filters, RRF fusion and deterministic tie-breaks.

FR-057/ER-03: hard filters (deleted/orphaned/secret) run first; keyword and
semantic candidate lists fuse via reciprocal rank fusion (k=60); deterministic
tie-break reasons order equal scores.
"""

from __future__ import annotations

from dataclasses import dataclass

_RRF_K = 60


@dataclass(frozen=True)
class RankedHit:
    object_id: object
    score: float
    reasons: tuple[str, ...]


def _hard_filter(hit: dict) -> bool:
    return hit.get("lifecycle_state") in {"deleted", "orphaned"} or hit.get("sensitivity") == "secret"


def rrf_fuse(*, keyword_rank: list[object], semantic_rank: list[object]) -> dict[object, float]:
    fused: dict[object, float] = {}
    for rank in (keyword_rank, semantic_rank):
        for position, object_id in enumerate(rank):
            fused[object_id] = fused.get(object_id, 0.0) + 1.0 / (_RRF_K + position + 1)
    return fused


def rank_hits(*, candidates: list[dict], keyword_rank: list[object], semantic_rank: list[object]) -> list[RankedHit]:
    eligible = [c for c in candidates if not _hard_filter(c)]
    if len(eligible) <= 1:
        return [RankedHit(object_id=c["id"], score=0.0, reasons=("single",)) for c in eligible]
    fused = rrf_fuse(keyword_rank=keyword_rank, semantic_rank=semantic_rank)
    scored = sorted(
        ((c["id"], fused.get(c["id"], 0.0), c.get("freshness") == "fresh") for c in eligible),
        key=lambda item: (-item[1], not item[2], str(item[0])),
    )
    return [RankedHit(object_id=object_id, score=score, reasons=("rrf",)) for object_id, score, _ in scored]