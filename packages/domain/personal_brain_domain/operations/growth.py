"""Bounded retention for logs, temporary data, notifications and rebuildable indexes.

FR-093: growth is controlled by per-category retention ceilings.
"""

from __future__ import annotations

from dataclasses import dataclass

_RETENTION_DAYS = {"logs": 30, "temporary": 24, "notifications": 90, "indexes": 0}


@dataclass(frozen=True)
class GrowthPolicy:
    retention_days: dict[str, int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "retention_days", dict(_RETENTION_DAYS))

    def keep(self, *, category: str, age_days: float) -> bool:
        ceiling = self.retention_days.get(category)
        if ceiling is None:
            raise ValueError("unknown growth category")
        return age_days <= ceiling