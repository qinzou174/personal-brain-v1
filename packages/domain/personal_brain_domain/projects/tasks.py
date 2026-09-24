"""Task start lifecycle with revision/dirty/constraint evidence.

FR-049/FR-050: a task may start only with a current revision and known dirty
state; the start evidence is captured once. Completion requires a final report.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectTask:
    task_id: object
    project_id: object
    goal: str
    state: str  # planned | active | paused | completed | failed | cancelled
    start_revision: str | None = None
    start_dirty_state: bool | None = None
    constraints: tuple[str, ...] = ()
    affected_modules: tuple[str, ...] = ()


def start_task(*, task_id, project_id, goal, revision, dirty_state) -> ProjectTask:
    if not revision or dirty_state is None:
        raise ValueError("task start requires revision and known dirty state")
    return ProjectTask(task_id=task_id, project_id=project_id, goal=goal, state="active",
                       start_revision=revision, start_dirty_state=dirty_state)