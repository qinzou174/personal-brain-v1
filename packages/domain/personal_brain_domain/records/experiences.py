"""Contextual Experience creation separated from objective Event facts.

FR-017/FR-024..FR-030: an experience is a subjective, context-bound expression
linked to exactly one objective event. By itself it is always a candidate and can
never establish a global preference without a separate evidence/promotion
decision.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class Experience:
    event_id: object
    user_expression: str
    context: str
    source_id: object
    experience_id: str
    normalized_interpretation: str | None = None
    confidence: str | None = None
    establishment: str = "candidate"


def create_experience(*, event_id: object, user_expression: str, context: str,
                      source_id: object, normalized_interpretation: str | None = None,
                      confidence: str | None = None) -> Experience:
    """Create a contextual experience; never a standalone global fact."""
    if not user_expression or not context:
        raise ValueError("experience requires expression and context")
    return Experience(
        event_id=event_id,
        user_expression=user_expression,
        context=context,
        source_id=source_id,
        experience_id=str(uuid.uuid4()),
        normalized_interpretation=normalized_interpretation,
        confidence=confidence,
        establishment="candidate",
    )
