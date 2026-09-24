"""Canonical/derived classification and append-only derivation versioning.

FR-005..FR-007/ER-01: canonical input is immutable; every derived object carries
generator identity and version, live source edges, and a state that orphans it
when the last live source disappears. Derived access is the intersection of the
source scopes and the maximum of the source sensitivities.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping, Sequence
from uuid import UUID, uuid4


def classify_canonicality(*, declared: str) -> str:
    if declared not in {"canonical", "derived"}:
        raise ValueError("canonicality must be canonical or derived")
    return declared


@dataclass(frozen=True)
class DerivationIdentity:
    """Identifies one immutable derivation generation."""

    derivation_id: UUID = None  # type: ignore[assignment]
    generator_kind: str = ""
    generator_version: str = ""
    derived_at: datetime = None  # type: ignore[assignment]
    source_edge_ids: tuple[UUID, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "derivation_id", self.derivation_id or uuid4())
        object.__setattr__(self, "derived_at", self.derived_at or datetime.now(timezone.utc))
        if not self.generator_kind or not self.generator_version:
            raise ValueError("generator identity is required")


def recalculate_derivation_state(
    *,
    current_state: str,
    live_source_ids: Sequence[UUID | str],
) -> str:
    """Active derived content loses all live sources -> orphaned; otherwise recomputing."""
    if current_state not in {"active", "orphaned", "recomputing", "superseded", "failed", "candidate"}:
        raise ValueError("unknown derived state")
    if not live_source_ids:
        return "orphaned"
    return "recomputing"


def derive_access_boundary(sources: Sequence[Mapping[str, object]]) -> "AccessBoundary":
    """Effective derived access is scope intersection and maximum sensitivity."""
    scopes = None
    sensitivity_rank = {"normal": 0, "personal": 1, "private": 2, "highly_private": 3}
    highest = "normal"
    for source in sources:
        source_scopes = source.get("scopes")
        if not isinstance(source_scopes, Iterable) or not source_scopes:
            raise ValueError("every source must declare at least one scope")
        current = frozenset(str(scope) for scope in source_scopes)
        scopes = current if scopes is None else scopes & current
        sensitivity = str(source.get("sensitivity", "normal"))
        if sensitivity not in sensitivity_rank:
            raise ValueError("unknown sensitivity")
        if sensitivity_rank[sensitivity] > sensitivity_rank[highest]:
            highest = sensitivity
    if scopes is None:
        raise ValueError("derived content requires sources")
    return AccessBoundary(scopes=scopes, sensitivity=highest)


@dataclass(frozen=True)
class AccessBoundary:
    scopes: frozenset[str]
    sensitivity: str


def next_derivation_version(*, current_version: str, generator_version: str) -> str:
    """Append-only versioning: a new generation is always distinguishable.

    The stored generation is a compound of generator version and a per-generation
    nonce so reprocessing with the same generator still produces a new version.
    """
    if not generator_version:
        raise ValueError("generator version is required")
    return f"{generator_version}:{current_version or 'v0'}:{uuid4().hex[:12]}"
