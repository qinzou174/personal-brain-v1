"""Hierarchical selection, deduplication and context compilation.

FR-058/FR-059/FR-061..FR-065: the compiler selects current-before-history
authority, deduplicates, links historical rationale and includes source links and
uncertainty warnings.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextPackage:
    intent: str
    current_state: tuple[object, ...]
    historical_rationale: tuple[object, ...]
    warnings: tuple[str, ...]
    source_references: tuple[object, ...]


def compile_context(*, intent: str, candidates: list[dict],
                    history_items: list[dict], warnings: list[str]) -> ContextPackage:
    seen = set()
    current = []
    for candidate in sorted(candidates, key=lambda c: c.get("freshness") == "fresh", reverse=True):
        if candidate["id"] in seen:
            continue
        seen.add(candidate["id"])
        current.append(candidate["id"])
    historical = [item["id"] for item in history_items if item["id"] not in seen]
    sources = tuple(c for c in candidates if c.get("source_ref") is not None)
    return ContextPackage(intent=intent, current_state=tuple(current),
                          historical_rationale=tuple(historical),
                          warnings=tuple(dict.fromkeys(warnings)),
                          source_references=tuple(s["source_ref"] for s in sources))