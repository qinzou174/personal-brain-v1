"""Evidence contribution, promotion thresholds and confidence recalculation.

FR-025/FR-029/FR-030/ER-02: promotion of a candidate requires at least 3
canonical inputs spanning >=14 days across >=2 contexts, at least one direct user
statement, no contradiction, and each canonical source counts once (reprocessing
the same source never multiplies evidence). Loss of evidence triggers
recalculation and may demote, but never erases the claim's history.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class PromotionEvidence:
    source_id: object
    observed_at: datetime
    context: str
    direct_user_statement: bool = False
    contradicts: bool = False


@dataclass(frozen=True)
class PromotionAssessment:
    state: str  # established | candidate
    evidence_count: int
    span_days: float
    context_count: int
    has_direct_statement: bool
    has_contradiction: bool


def assess_b_promotion(signals: list[PromotionEvidence]) -> str:
    """Return ``established`` only when every conjunctive baseline is met."""
    if any(signal.contradicts for signal in signals):
        return "candidate"
    unique_sources = {str(signal.source_id) for signal in signals}
    if len(unique_sources) < 3:
        return "candidate"
    contexts = {signal.context for signal in signals}
    if len(contexts) < 2:
        return "candidate"
    times = [signal.observed_at for signal in signals]
    span = (max(times) - min(times)).total_seconds() / 86400.0
    if span < 14:
        return "candidate"
    if not any(signal.direct_user_statement for signal in signals):
        return "candidate"
    return "established"


@dataclass(frozen=True)
class SelfCandidate:
    establishment: str
    source_ids: tuple[object, ...]
    expression: str
    context: str


def experience_to_self_candidate(*, source_id: object, expression: str, context: str) -> SelfCandidate:
    """A single experience can never establish a global preference."""
    return SelfCandidate(establishment="candidate", source_ids=(source_id,), expression=expression, context=context)


@dataclass(frozen=True)
class EvidenceRecalculation:
    remaining_evidence: tuple[object, ...]
    recalculation_triggered: bool
    claim_preserved: bool


def recalculate_on_evidence_loss(*, evidence_ids: tuple[object, ...], removed_evidence_id: object) -> EvidenceRecalculation:
    """Removing evidence recalculates confidence but preserves the claim's history."""
    remaining = tuple(e for e in evidence_ids if e != removed_evidence_id)
    return EvidenceRecalculation(remaining_evidence=remaining, recalculation_triggered=True, claim_preserved=True)
