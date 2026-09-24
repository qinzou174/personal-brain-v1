"""Conflict detection and time/user/tolerated resolution without participant loss.

FR-077/FR-078: a conflict opens with at least two participants; resolution never
silently deletes a participant.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConflictResolution:
    state: str  # resolved_by_time | resolved_by_user | tolerated | superseded
    participants: tuple[object, ...]
    resolution: str = ""


def resolve_conflict(*, participants: tuple[object, ...], mode: str,
                     resolution: str = "") -> ConflictResolution:
    if len(participants) < 2:
        raise ValueError("conflict requires at least two participants")
    if mode == "time":
        return ConflictResolution(state="resolved_by_time", participants=participants, resolution=resolution)
    if mode == "user":
        return ConflictResolution(state="resolved_by_user", participants=participants, resolution=resolution)
    if mode == "tolerate":
        return ConflictResolution(state="tolerated", participants=participants, resolution=resolution)
    raise ValueError("unknown conflict resolution mode")