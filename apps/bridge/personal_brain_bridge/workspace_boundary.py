"""Normalized workspace-root containment including link/reparse resolution.

FR-055: the bridge observes only an approved workspace root. Every path is
resolved lexically and then by real filesystem identity so symlinks, junctions
and reparse points cannot escape the approved root.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from personal_brain_domain.common.errors import BrainError


def normalize_root(root: Path) -> Path:
    """Return an absolute, real (symlink-free) identity for the approved root."""
    resolved = root.resolve(strict=False)
    return resolved


def _is_same_tree(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_within_workspace(root: Path, requested: Path) -> Path:
    """Resolve ``requested`` against ``root`` and reject any escape.

    Steps: lexical join, then ``resolve`` to a real identity, then re-check the
    real identity is still under the real root. This closes ``..``, absolute-path
    substitution and symlink/reparse-point escapes.
    """
    root = normalize_root(root)
    candidate = root / requested
    real_candidate = candidate.resolve(strict=False)
    if not _is_same_tree(real_candidate, root):
        raise BrainError("WORKSPACE_BOUNDARY_VIOLATION")
    return real_candidate
