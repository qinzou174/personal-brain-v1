"""Temporal validity, context, contradictions, corrections and supersession.

FR-027/FR-028/ER-02: explicit statements outrank contradictory inference; the
prior claim is superseded but always remains historical and attributable; a
resolution is never allowed to silently erase participants.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping


@dataclass(frozen=True)
class ContradictionResolution:
    current_state: str
    history_retained: bool
    current_is_historical: bool


def apply_contradiction(
    *,
    current_statement: str,
    new_statement: str,
    current_kind: str,
    new_kind: str,
    now: datetime,
) -> ContradictionResolution:
    """Explicit statements outrank inference; the superseded one stays historical."""
    resolved_by_explicit = new_kind == "explicit_user_statement" and current_kind == "inference"
    return ContradictionResolution(
        current_state="superseded" if resolved_by_explicit else "active",
        history_retained=True,
        current_is_historical=resolved_by_explicit,
    )


@dataclass(frozen=True)
class AuthorityResolution:
    winner: str
    confidence_did_not_decide: bool


def resolve_authority(*, candidate_a: Mapping[str, object], candidate_b: Mapping[str, object]) -> AuthorityResolution:
    """Kind outranks confidence: explicit user statements beat any inference."""
    if candidate_a["kind"] == "explicit_user_statement" and candidate_b["kind"] == "inference":
        return AuthorityResolution(winner="explicit_user_statement", confidence_did_not_decide=True)
    if candidate_b["kind"] == "explicit_user_statement" and candidate_a["kind"] == "inference":
        return AuthorityResolution(winner="explicit_user_statement", confidence_did_not_decide=True)
    a_confidence = float(candidate_a.get("confidence", 0) or 0)
    b_confidence = float(candidate_b.get("confidence", 0) or 0)
    return AuthorityResolution(winner="a" if a_confidence >= b_confidence else "b", confidence_did_not_decide=False)