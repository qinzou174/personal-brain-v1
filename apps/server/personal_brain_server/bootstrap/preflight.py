"""Minimal DB/job readiness preflight.

FR-083/FR-092: the Brain reports readiness only with evidence. Components are
checked independently; a failure in one component never collapses into HTTP
availability, and nothing is claimed ready without a verified check.
"""

from __future__ import annotations

from typing import Mapping


def preflight_report(*, database: str, worker: str, storage: str) -> dict[str, object]:
    """Assemble a value-free readiness report from per-component checks.

    Each component value is one of ``ok | failed | unchecked``; the overall
    ``ready`` flag requires every component to be ``ok``.
    """
    components = {"database": database, "worker": worker, "storage": storage}
    for name, value in components.items():
        if value not in {"ok", "failed", "unchecked"}:
            raise ValueError(f"unknown preflight state for {name}")
    ready = all(value == "ok" for value in components.values())
    return {"ready": ready, **components}
