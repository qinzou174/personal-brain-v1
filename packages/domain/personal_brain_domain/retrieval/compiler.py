"""Hierarchical selection, deduplication and context compilation.

FR-058/FR-059/FR-061..FR-065: the compiler selects current-before-history
authority, deduplicates, links historical rationale and includes source links and
uncertainty warnings. It delegates ranking decisions to the ranking module so
ordering and its reasons stay consistent (ER-03).
"""

from __future__ import annotations

from dataclasses import dataclass

from personal_brain_domain.retrieval.ranking import rank_hits


@dataclass(frozen=True)
class ContextPackage:
    intent: str
    current_state: tuple[object, ...]
    historical_rationale: tuple[object, ...]
    warnings: tuple[str, ...]
    source_references: tuple[object, ...]
    ranking_reasons: tuple[tuple[str, ...], ...] = ()


def compile_context(*, intent: str, candidates: list[dict],
                    history_items: list[dict], warnings: list[str],
                    keyword_rank: list[object] | None = None,
                    semantic_rank: list[object] | None = None) -> ContextPackage:
    seen = set()
    current = []
    reasons_by_id: dict[object, tuple[str, ...]] = {}
    ranked = rank_hits(
        candidates=candidates,
        keyword_rank=list(keyword_rank) if keyword_rank else [c["id"] for c in candidates],
        semantic_rank=list(semantic_rank) if semantic_rank else [],
    )
    for hit in ranked:
        if hit.object_id in seen:
            continue
        seen.add(hit.object_id)
        current.append(hit.object_id)
        reasons_by_id[hit.object_id] = hit.reasons
    # Fallback: candidates excluded by rank_hits hard filter never appear here
    # because rank_hits already removed them; history items dedupe against seen.
    historical = [item["id"] for item in history_items if item["id"] not in seen]
    sources = tuple(c for c in candidates if c.get("source_ref") is not None)
    return ContextPackage(intent=intent, current_state=tuple(current),
                          historical_rationale=tuple(historical),
                          warnings=tuple(dict.fromkeys(warnings)),
                          source_references=tuple(s["source_ref"] for s in sources),
                          ranking_reasons=tuple(reasons_by_id[id_] for id_ in current))