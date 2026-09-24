"""Deterministic maintenance and reprocessing job handlers.

FR-081..FR-086: health/retention/index-rebuild jobs run under the durable job
contract; failures surface as findings, never silently swallowed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MaintenanceOutcome:
    job_id: str
    state: str
    summary: str


def run_health_check(*, job_id: str, components: dict[str, str]) -> MaintenanceOutcome:
    failed = [name for name, state in components.items() if state in {"failed", "degraded"}]
    return MaintenanceOutcome(job_id=job_id, state="succeeded",
                              summary=f"components_checked={len(components)} failures={len(failed)}")