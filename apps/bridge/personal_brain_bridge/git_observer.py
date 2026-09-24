"""Bounded Git revision/status/change/hash observation."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from personal_brain_bridge.bootstrap_scan import MAX_FILE_BYTES, excluded
from personal_brain_bridge.workspace_boundary import normalize_root, resolve_within_workspace

MAX_CHANGED_PATHS = 1_000
MAX_HASH_ENTRIES = 5_000


@dataclass(frozen=True)
class ChangeEvidence:
    revision: str | None
    branch: str | None
    dirty: bool | None
    changed_paths: tuple[str, ...]
    file_hashes: dict[str, str] = field(default_factory=dict)
    available: bool = True

    def __post_init__(self) -> None:
        if len(self.changed_paths) > MAX_CHANGED_PATHS or len(self.file_hashes) > MAX_HASH_ENTRIES:
            raise ValueError("git evidence exceeds documented bound")


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=10, check=True,
    )
    # Porcelain status uses its leading two columns as data; never lstrip it.
    return completed.stdout.rstrip("\r\n")


def observe_repository(path: str | Path, *, since_revision: str | None = None) -> ChangeEvidence:
    """Read current Git evidence without reading file contents outside the approved root."""
    try:
        root = normalize_root(Path(path))
        if not root.is_dir():
            raise OSError("missing root")
        top = normalize_root(Path(_git(root, "rev-parse", "--show-toplevel")))
        if top != root:
            raise ValueError("approved root must be the repository root")
        revision = _git(root, "rev-parse", "HEAD")
        branch = _git(root, "branch", "--show-current") or None
        status = _git(root, "status", "--porcelain=v1", "-z")
        paths: set[str] = set()
        records = [record for record in status.split("\0") if record]
        index = 0
        while index < len(records):
            record = records[index]
            if len(record) >= 4:
                paths.add(record[3:].replace("\\", "/"))
                if record[:2] in {"R ", "C ", "RM", "CM"} and index + 1 < len(records):
                    index += 1
                    paths.add(records[index].replace("\\", "/"))
            index += 1
        if since_revision:
            diff = _git(root, "diff", "--name-only", "--diff-filter=ACDMRTUXB", f"{since_revision}..HEAD")
            paths.update(line.replace("\\", "/") for line in diff.splitlines() if line)
        bounded = tuple(sorted(paths))[:MAX_CHANGED_PATHS]
        hashes: dict[str, str] = {}
        for relative in bounded[:MAX_HASH_ENTRIES]:
            if any(excluded(part) for part in Path(relative).parts):
                continue
            candidate = resolve_within_workspace(root, Path(relative))
            if candidate.is_file() and not candidate.is_symlink() and candidate.stat().st_size <= MAX_FILE_BYTES:
                hashes[relative] = hashlib.sha256(candidate.read_bytes()).hexdigest()
        return ChangeEvidence(
            revision=revision, branch=branch, dirty=bool(status),
            changed_paths=bounded, file_hashes=hashes,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return ChangeEvidence(revision=None, branch=None, dirty=None, changed_paths=(), available=False)
