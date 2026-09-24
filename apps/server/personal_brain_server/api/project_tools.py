"""Project/task/module/recent-change read and write operations.

FR-041..FR-053/FR-099: the project API exposes the recovery package to a fresh
client, task start/checkpoint/finalize, and module freshness. Grants are
project-scoped; reads require ``project.read:<id>``, writes ``project.write:<id>``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from personal_brain_domain.common.errors import BrainError


def _require_project_grant(grants: list[dict], *, client_id: str, tool: str, project_id: str) -> None:
    allowed = False
    for grant in grants:
        if grant.get("client_id") != client_id:
            continue
        if grant.get("effect") == "deny":
            raise BrainError("TOOL_DENIED")
        pattern = grant.get("project", "")
        if grant.get("tool_pattern") == tool and pattern == project_id:
            allowed = True
    if not allowed:
        raise BrainError("SCOPE_DENIED")


@dataclass
class ProjectStore:
    projects: dict = field(default_factory=dict)
    tasks: dict = field(default_factory=dict)
    checkpoints: dict = field(default_factory=dict)
    modules: dict = field(default_factory=dict)


_STORE: ProjectStore | None = None
_AUTHORITATIVE_REPOSITORY: object | None = None


def configure_authoritative_repository(repository: object) -> None:
    global _STORE, _AUTHORITATIVE_REPOSITORY
    _STORE = None
    _AUTHORITATIVE_REPOSITORY = repository


def _memory_store() -> ProjectStore:
    if _STORE is None:
        raise BrainError("BRAIN_UNAVAILABLE")
    return _STORE


def reset_store() -> None:
    global _STORE, _AUTHORITATIVE_REPOSITORY
    _AUTHORITATIVE_REPOSITORY = None
    _STORE = ProjectStore()


def register_project(*, project_id: str, name: str, purpose: str, owner_id: str = "owner-1",
                     idempotency_key: str | None = None) -> None:
    if _AUTHORITATIVE_REPOSITORY is not None:
        if idempotency_key is None:
            raise BrainError("VALIDATION_FAILED")
        _AUTHORITATIVE_REPOSITORY.create_project(
            name=name, purpose=purpose, requested_scope=f"project:{project_id}",
            idempotency_key=uuid.UUID(idempotency_key),
        )
        return
    store = _memory_store()
    store.projects[project_id] = {"project_id": project_id, "name": name, "purpose": purpose, "owner_id": owner_id}


def start_task(*, client_id: str, grants: list[dict], project_id: str, goal: str, revision: str,
               dirty_state: bool, constraints: tuple[str, ...] = (), idempotency_key: str | None = None) -> dict:
    _require_project_grant(grants, client_id=client_id, tool="project.write", project_id=project_id)
    if _AUTHORITATIVE_REPOSITORY is not None:
        if idempotency_key is None:
            raise BrainError("VALIDATION_FAILED")
        return _AUTHORITATIVE_REPOSITORY.start_project_task(
            project_id=uuid.UUID(project_id), goal=goal, revision=revision,
            dirty_state=dirty_state, constraints=list(constraints),
            idempotency_key=uuid.UUID(idempotency_key),
        )
    store = _memory_store()
    from personal_brain_domain.projects.tasks import start_task as domain_start

    task = domain_start(task_id=f"task-{len(store.tasks) + 1}", project_id=project_id, goal=goal,
                        revision=revision, dirty_state=dirty_state)
    record = {"task_id": task.task_id, "project_id": project_id, "goal": goal, "state": "active",
              "start_revision": revision, "start_dirty_state": dirty_state, "constraints": list(constraints)}
    store.tasks[task.task_id] = record
    return record


def checkpoint_task(*, client_id: str, grants: list[dict], project_id: str, task_id: str,
                    completed_work: str, next_step: str = "", problems: str = "",
                    revision: str | None = None, idempotency_key: str | None = None) -> dict:
    _require_project_grant(grants, client_id=client_id, tool="project.write", project_id=project_id)
    if _AUTHORITATIVE_REPOSITORY is not None:
        if idempotency_key is None:
            raise BrainError("VALIDATION_FAILED")
        return _AUTHORITATIVE_REPOSITORY.checkpoint_project_task(
            task_id=uuid.UUID(task_id), completed_work=completed_work, next_step=next_step,
            problems=problems, revision=revision, idempotency_key=uuid.UUID(idempotency_key),
        )
    store = _memory_store()
    from personal_brain_domain.projects.checkpoints import capture_checkpoint

    checkpoint = capture_checkpoint(task_id=task_id, completed_work=completed_work,
                                    next_step=next_step, problems=problems)
    record = {"checkpoint_id": checkpoint.checkpoint_id, "task_id": task_id,
              "completed_work": completed_work, "next_step": next_step}
    store.checkpoints[checkpoint.checkpoint_id] = record
    return record


def get_recovery(*, client_id: str, grants: list[dict], project_id: str) -> dict:
    _require_project_grant(grants, client_id=client_id, tool="project.read", project_id=project_id)
    if _AUTHORITATIVE_REPOSITORY is not None:
        return _AUTHORITATIVE_REPOSITORY.get_project_recovery(uuid.UUID(project_id))
    store = _memory_store()
    project = store.projects.get(project_id)
    if project is None:
        raise BrainError("NOT_FOUND")
    active = next((t for t in store.tasks.values() if t["project_id"] == project_id and t["state"] == "active"), None)
    checkpoint_records = [c for c in store.checkpoints.values() if active and c["task_id"] == active["task_id"]]
    return {
        "project_purpose": project["purpose"],
        "active_task": active,
        "checkpoints": checkpoint_records,
        "next_step": checkpoint_records[-1]["next_step"] if checkpoint_records else "inspect current source before further modification",
    }
