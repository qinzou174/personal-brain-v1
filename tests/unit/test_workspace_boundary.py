"""Workspace root containment with link/reparse resolution (T034, FR-055)."""

from pathlib import Path

import pytest


def test_inside_and_relative_escaping():
    from personal_brain_bridge.workspace_boundary import resolve_within_workspace

    root = Path("/home/kms/workspace").resolve()
    assert resolve_within_workspace(root, Path("sub/file.txt")).relative_to(root)
    assert resolve_within_workspace(root, Path("./file.txt")).relative_to(root)
    with pytest.raises(Exception):
        resolve_within_workspace(root, Path("../outside.txt"))


def test_absolute_escape_and_lexical_attack():
    from personal_brain_bridge.workspace_boundary import resolve_within_workspace

    root = Path("/home/kms/workspace").resolve()
    with pytest.raises(Exception):
        resolve_within_workspace(root, Path("/etc/passwd"))
    with pytest.raises(Exception):
        resolve_within_workspace(root, Path("sub/../../outside.txt"))
