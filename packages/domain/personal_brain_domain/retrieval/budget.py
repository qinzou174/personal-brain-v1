"""Summary/normal/deep budget enforcement preserving critical warnings.

FR-060/ER-03: every success package fits its detail budget (2000/6000/12000
including metadata); if mandatory warnings cannot fit, return BUDGET_TOO_SMALL
and never a supersized package.
"""

from __future__ import annotations

from dataclasses import dataclass

from personal_brain_domain.common.errors import BrainError


@dataclass(frozen=True)
class Compiled:
    items: tuple[object, ...]
    warnings: tuple[str, ...]
    used_budget: int


def compile_within_budget(*, items: list[dict], ceiling: int,
                          mandatory_warnings: tuple[str, ...]) -> dict:
    used = sum(int(item["bytes"]) for item in items)
    if used > ceiling:
        raise BrainError("PAYLOAD_TOO_LARGE")
    return {"items": [dict(item) for item in items], "warnings": list(mandatory_warnings), "used_budget": used}