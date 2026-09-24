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


def _signal_reasons(hit: dict) -> tuple[str, ...]:
    """Collect the input signals that influenced ranking (ER-03).

    Every returned reason names a concrete input (freshness / confidence /
    source class / source trust) so a client or audit can explain "why this
    hit ranks here". Unknown signals yield an empty tuple and callers fall
    back to their stable default reason.
    """
    reasons: list[str] = []
    freshness = hit.get("freshness")
    if freshness:
        reasons.append(f"freshness={freshness}")
    confidence = hit.get("confidence")
    if isinstance(confidence, (int, float)):
        reasons.append(f"confidence={confidence:g}")
    info_class = hit.get("information_class")
    if info_class:
        reasons.append(f"source={info_class}")
    source_trust = hit.get("source_trust")
    if source_trust:
        reasons.append(f"source_trust={source_trust}")
    return tuple(reasons)


def rrf_fuse(*, keyword_rank: list[object], semantic_rank: list[object]) -> dict[object, float]:
    fused: dict[object, float] = {}
    for rank in (keyword_rank, semantic_rank):
        for position, object_id in enumerate(rank):
            fused[object_id] = fused.get(object_id, 0.0) + 1.0 / (_RRF_K + position + 1)
    return fused


def rank_hits(*, candidates: list[dict], keyword_rank: list[object], semantic_rank: list[object]) -> list[RankedHit]:
    eligible = [c for c in candidates if not _hard_filter(c)]
    if not eligible:
        return []
    if len(eligible) == 1:
        c = eligible[0]
        reasons = _signal_reasons(c) or ("single",)
        return [RankedHit(object_id=c["id"], score=0.0, reasons=reasons)]
    fused = rrf_fuse(keyword_rank=keyword_rank, semantic_rank=semantic_rank)
    scored = sorted(
        ((c["id"], fused.get(c["id"], 0.0), c.get("freshness") == "fresh") for c in eligible),
        key=lambda item: (-item[1], not item[2], str(item[0])),
    )
    by_id = {c["id"]: c for c in eligible}
    ranked: list[RankedHit] = []
    for object_id, score, _ in scored:
        reasons = _signal_reasons(by_id[object_id]) or ("rrf",)
        ranked.append(RankedHit(object_id=object_id, score=score, reasons=reasons))
    return ranked