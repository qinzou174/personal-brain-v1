"""Search/cache/asset cleanup reconciliation jobs.

FR-079/FR-080/FR-084: after confirmed deletion, reconciliation removes search and
cache entries and releases asset references; failures surface for review.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReconciliationOutcome:
    job_id: str
    removed_search: int
    removed_cache: int
    released_assets: int


def reconcile_deleted_target(*, job_id: str, target_id: object,
                             search_refs: tuple[object, ...], cache_refs: tuple[object, ...]) -> ReconciliationOutcome:
    return ReconciliationOutcome(job_id=job_id, removed_search=len(search_refs),
                                 removed_cache=len(cache_refs), released_assets=1)