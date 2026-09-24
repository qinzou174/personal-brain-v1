"""Class A/B/C classification, candidate-first preferences and confirmation gates.

FR-023..FR-028/ER-02/ER-06: explicit-remember ordinary statements become active
class A; ordinary signals become class B candidates; core identity/value changes
are class C and require owner confirmation bound to the proposal. Imported or
model text never counts as owner confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass

_CONFIRMATION_SOURCES = frozenset({"explicit_user_statement"})


@dataclass(frozen=True)
class SelfClassification:
    policy_class: str  # A | B | C
    lifecycle: str
    establishment: str  # explicit | candidate


def can_activate(*, policy_class: str, owner_confirmed: bool, source_kind: str) -> bool:
    """Class C can never activate without owner confirmation from the right source."""
    if policy_class == "C":
        return owner_confirmed and source_kind in _CONFIRMATION_SOURCES
    return True


def classify_and_activate(
    *,
    text: str,
    explicit_remember: bool,
    high_impact: bool,
    owner_confirmed: bool,
) -> SelfClassification:
    """ER-02 precedence: C high-impact before A explicit before B ordinary."""
    if high_impact:
        return SelfClassification(policy_class="C", lifecycle="active" if can_activate(policy_class="C", owner_confirmed=owner_confirmed, source_kind="explicit_user_statement") else "pending_confirmation", establishment="explicit" if owner_confirmed else "candidate")
    if explicit_remember:
        return SelfClassification(policy_class="A", lifecycle="active", establishment="explicit")
    return SelfClassification(policy_class="B", lifecycle="candidate", establishment="candidate")
