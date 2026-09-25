"""Deterministic claim polarity heuristics shared by worker and store.

Topic signatures are a deliberately simple heuristic (normalize
punctuation/whitespace, then remove negation markers), so the same text with
and without a negation compares as one topic with opposite polarity. The
worker's batch ``conflict_scan`` and the store's real-time ``conflict_warning``
hint MUST agree on this rule — otherwise a contradiction flagged at write time
could silently disagree with the overnight scan (or vice versa).
"""

from __future__ import annotations

from typing import Any

NEGATION_MARKERS = ("不再", "再也不", "不", "没", "讨厌", "戒", "拒绝", "放弃")
_PUNCTUATION = frozenset(
    "，。！？、；：“”‘’（）《》【】「」…—·,.!?;:'\"()[]{}<>~`@#$%^&*_-+=|\\/ \t\n\r\u3000"
)


def normalize_claim(text: Any) -> str:
    """Lowercase and drop whitespace/punctuation so surface form never matters."""
    return "".join(character for character in str(text or "").lower()
                   if character not in _PUNCTUATION)


def is_negative(text: Any) -> bool:
    normalized = normalize_claim(text)
    return any(marker in normalized for marker in NEGATION_MARKERS)


def topic_key(text: Any) -> str:
    """The claim's topic: normalized text without negation markers."""
    normalized = normalize_claim(text)
    for marker in NEGATION_MARKERS:
        normalized = normalized.replace(marker, "")
    return normalized
