"""Memory lifecycle and policy-specific retention.

FR-021/FR-022/ER-02: B candidates expire at 90 days without promotion;
established B memories become historical after 180 days; explicit (class A)
memories never age into unconfirmed expiry.
"""

from __future__ import annotations

from datetime import datetime


def validate_memory_lifecycle(*, state: str, expires_at: datetime | None) -> None:
    if state == "temporary" and expires_at is None:
        raise ValueError("temporary memory requires an expiry")


def retention_transition(
    current: str,
    *,
    last_supported_at: datetime,
    now: datetime,
    policy_class: str | None = None,
) -> str:
    """Return the next lifecycle state from age and class policy."""
    if policy_class == "A" and current == "active":
        return "active"  # explicit class-A memory does not age into expiry
    age_days = (now - last_supported_at).total_seconds() / 86400.0
    if current == "candidate":
        return "expired" if age_days > 90 else "candidate"
    if current == "established":
        return "historical" if age_days > 180 else "established"
    return current
