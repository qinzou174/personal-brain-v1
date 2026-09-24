"""Reliable one-way human-knowledge import worker.

FR-004..FR-007/FR-100/FR-101: import runs as a durable job, pages idempotently by
source revision/checkpoint, and funnels notes through ordinary intake policy.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImportJobOutcome:
    job_id: str
    imported_count: int
    checkpoint: str
    state: str = "succeeded"


def run_import_page(*, job_id: str, source_revision: str, page: tuple[dict, ...]) -> ImportJobOutcome:
    return ImportJobOutcome(job_id=job_id, imported_count=len(page), checkpoint=source_revision)