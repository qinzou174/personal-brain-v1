"""Priority, cooldown, merge, dedupe, preference and channel policy.

FR-091/ER-11: 10-minute merge window, 60-minute cooldown, daily persistent recap;
date-only 09:00 scheduling never invents a due time.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SendDecision:
    send: bool
    reason: str


def decide_send(*, dedupe_key: str, last_sent_minutes_ago: float, cooldown_minutes: float = 60) -> SendDecision:
    if last_sent_minutes_ago < cooldown_minutes:
        return SendDecision(send=False, reason="within_cooldown_merged")
    return SendDecision(send=True, reason="eligible")