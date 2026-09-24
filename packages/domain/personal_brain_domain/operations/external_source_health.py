"""Optional source health and last-import status without core readiness dependency.

FR-100: the human-knowledge interface may be disabled; core Brain behavior stays
available and the health view reports the interface honestly.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExternalHealth:
    core_available: bool
    external: str
    last_import_at: object | None = None
    last_import_status: str | None = None


def core_without_external(*, interface_enabled: bool) -> dict[str, object]:
    return {
        "core_available": True,
        "external": "enabled" if interface_enabled else "disabled",
    }