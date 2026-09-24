"""Incremental changed-file mapping and affected-module invalidation.

FR-047/FR-048/ER-08: only changed files since the last observation are mapped to
modules; a change invalidates only the modules whose files it touches.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IncrementalChange:
    changed_paths: tuple[str, ...]
    affected_modules: tuple[str, ...]
    revision: str | None
    dirty_state: bool | None


def map_changes(*, changed_paths: tuple[str, ...], module_paths: dict[str, tuple[str, ...]],
                revision: str | None, dirty_state: bool | None) -> IncrementalChange:
    affected = []
    for module, paths in module_paths.items():
        if any(
            changed == prefix.rstrip("/") or changed.startswith(prefix.rstrip("/") + "/")
            for changed in changed_paths for prefix in paths
        ):
            affected.append(module)
    return IncrementalChange(changed_paths=changed_paths, affected_modules=tuple(affected),
                             revision=revision, dirty_state=dirty_state)
