"""Project Brain continuity: project/profile invariants.

FR-041/FR-042: a project owns its purpose, goals, principles, workspace
identity and lifecycle; the profile is a single authoritative source for the
Brain's own project work.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Project:
    project_id: object
    name: str
    purpose: str
    goals: tuple[str, ...] = ()
    principles: tuple[str, ...] = ()
    workspace_identity: str | None = None
    lifecycle_state: str = "active"


def validate_project_invariants(*, name: str, purpose: str) -> None:
    if not name or not purpose:
        raise ValueError("project requires a name and purpose")
    if len(name) > 512 or len(purpose) > 4096:
        raise ValueError("project name or purpose exceeds bound")
