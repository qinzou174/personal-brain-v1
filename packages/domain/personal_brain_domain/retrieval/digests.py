"""Source-linked derived digest navigation (optional; cannot gate V1).

FR-102: automatic daily/weekly/monthly digests are OPTIONAL. The navigation
contract keeps digests source-linked and versioned when enabled.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Digest:
    digest_id: str
    kind: str  # daily | weekly | monthly
    source_ids: tuple[object, ...]
    generated_at: object
    generator_version: str


def build_digest(*, digest_id: str, kind: str, source_ids: tuple[object, ...],
                 generated_at: object, generator_version: str) -> Digest:
    if kind not in {"daily", "weekly", "monthly"}:
        raise ValueError("unknown digest kind")
    return Digest(digest_id=digest_id, kind=kind, source_ids=source_ids,
                  generated_at=generated_at, generator_version=generator_version)