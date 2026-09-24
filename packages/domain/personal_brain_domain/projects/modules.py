"""ModuleCard fields and fresh/stale/unknown transitions.

FR-043/FR-044/FR-048/ER-08: a module is fresh only with evidence that its indexed
revision equals the current one; stale when evidence differs; unknown when no
evidence exists. Racing refresh stays stale/unknown; it never pretends fresh.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleCard:
    module_id: object
    project_id: object
    name: str
    paths: tuple[str, ...] = ()
    responsibility: str = ""
    core_files: tuple[str, ...] = ()
    freshness: str = "unknown"
    indexed_revision: str | None = None
    stale_reasons: tuple[str, ...] = ()


def freshness_from_revision(*, indexed_revision, current_revision) -> str:
    if indexed_revision is None or current_revision is None:
        return "unknown"
    return "fresh" if indexed_revision == current_revision else "stale"


def freshness_for(evidence) -> str:
    """unknown unless explicit evidence exists; never guess fresh."""
    if not evidence or "fresh" not in evidence:
        return "unknown"
    return "fresh" if evidence["fresh"] is True else "stale"


def stale_warnings(*, module: str, freshness: str):
    if freshness == "stale":
        return {"module": module, "warning": "stale", "reason": "workspace evidence changed since indexing"}
    return None
