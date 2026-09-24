"""Fresh-client recovery package assembly.

FR-053/FR-054: a client with no chat history recovers the active task, checkpoints,
relevant modules, recent changes and current source evidence — never a fake
"fresh" claim. The next step is derived from the last checkpoint or remaining work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping


def assemble_recovery_package(
    *,
    project: Mapping[str, object],
    active_task: Mapping[str, object] | None,
    checkpoints: tuple[object, ...],
    relevant_modules: Mapping[str, str],
    recent_changes: tuple[object, ...],
    revision_evidence: Mapping[str, object],
    now: datetime,
) -> dict[str, object]:
    active = dict(active_task) if active_task else None
    next_step = active.get("remaining_work") if active else None
    if not next_step and checkpoints:
        last = checkpoints[-1]
        next_step = getattr(last, "next_step", None) or ""
    return {
        "project_purpose": project.get("purpose"),
        "active_task": active,
        "checkpoints": list(checkpoints),
        "relevant_modules": dict(relevant_modules),
        "recent_changes": list(recent_changes),
        "revision": revision_evidence.get("revision"),
        "dirty": revision_evidence.get("dirty"),
        "next_step": next_step or "inspect current source before further modification",
        "recovered_at": now.isoformat(),
    }