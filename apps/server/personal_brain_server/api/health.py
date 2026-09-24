"""Health API/tool response without collapsing failures into HTTP availability.

FR-092: component failures are reported per component; the HTTP endpoint stays
up while the health payload shows the failing components.
"""

from __future__ import annotations

from personal_brain_domain.operations.doctor import aggregate_health


def health_response(*, components: dict[str, str]) -> dict[str, object]:
    """Return per-component states plus overall; never masks failures."""
    report = aggregate_health(components=components)
    return {
        "service": "available",
        "overall": report["overall"],
        "components": report["components"],
    }