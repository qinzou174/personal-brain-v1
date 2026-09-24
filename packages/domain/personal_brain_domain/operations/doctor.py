"""Deterministic doctor checks.

FR-081/FR-082/FR-092: doctor reports per-component state without collapsing
failures into HTTP availability; findings are value-free.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    component: str
    severity: str
    message: str


def aggregate_health(*, components: dict[str, str]) -> dict[str, object]:
    if "failed" in components.values():
        overall = "failed"
    elif "degraded" in components.values():
        overall = "degraded"
    else:
        overall = "healthy"
    return {"overall": overall, "components": dict(components)}


def check_components(*, disk_free_percent: float, assets_corrupted: tuple[str, ...],
                     relations_broken: int) -> list[str]:
    findings = []
    if disk_free_percent <= 5:
        findings.append("disk:critical:free space critical")
    elif disk_free_percent <= 15:
        findings.append("disk:warn:free space low")
    if assets_corrupted:
        findings.append("assets:critical:corrupt asset detected")
    if relations_broken:
        findings.append("relations:warn:broken relation detected")
    return findings