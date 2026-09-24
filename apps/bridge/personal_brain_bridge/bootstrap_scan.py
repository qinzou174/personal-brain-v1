"""Bounded, secret-safe workspace bootstrap discovery."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from personal_brain_bridge.workspace_boundary import normalize_root, resolve_within_workspace

_EXCLUDED_NAMES = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".idea", ".trae",
    ".specify", "dist", "build", ".env", ".env.example", ".secrets",
    "credentials", "secrets", "coverage", ".pytest_cache", ".mypy_cache",
})
_EXCLUDED_SUFFIXES = frozenset({
    ".key", ".pem", ".p12", ".pfx", ".sqlite", ".db", ".log", ".bin",
    ".onnx", ".pt", ".safetensors", ".zip", ".tar", ".gz",
})
MAX_FILES_PER_MODULE = 500
MAX_FILE_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class ModuleEvidence:
    name: str
    paths: tuple[str, ...]
    core_files: tuple[str, ...]
    file_hashes: dict[str, str]


@dataclass(frozen=True)
class BootstrapScan:
    profile: dict = field(default_factory=dict)
    modules: tuple[str, ...] = ()
    module_evidence: tuple[ModuleEvidence, ...] = ()
    dependencies: dict[str, tuple[str, ...]] = field(default_factory=dict)
    risks: tuple[str, ...] = ()
    skipped_count: int = 0


def excluded(name: str) -> bool:
    lowered = name.lower()
    return lowered in _EXCLUDED_NAMES or Path(lowered).suffix in _EXCLUDED_SUFFIXES


def _safe_files(root: Path, module: Path) -> tuple[list[Path], int]:
    found: list[Path] = []
    skipped = 0
    pending = [module]
    while pending and len(found) < MAX_FILES_PER_MODULE:
        current = pending.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda item: item.name.casefold())
        except OSError:
            skipped += 1
            continue
        for entry in entries:
            if excluded(entry.name) or entry.is_symlink():
                skipped += 1
                continue
            try:
                safe = resolve_within_workspace(root, entry.relative_to(root))
                if safe.is_dir():
                    pending.append(safe)
                elif safe.is_file() and safe.stat().st_size <= MAX_FILE_BYTES:
                    found.append(safe)
                elif safe.is_file():
                    skipped += 1
            except (OSError, ValueError):
                skipped += 1
            if len(found) >= MAX_FILES_PER_MODULE:
                break
    return found, skipped


def scan_workspace(*, root_path: str, max_modules: int = 100) -> BootstrapScan:
    """Discover modules below exactly one approved root and hash bounded source files."""
    if max_modules < 1 or max_modules > 1000:
        raise ValueError("max_modules out of bounds")
    root = normalize_root(Path(root_path))
    if not root.is_dir():
        raise ValueError("approved workspace root must be an existing directory")
    candidates: list[Path] = []
    skipped = 0
    for entry in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        if excluded(entry.name) or entry.is_symlink():
            skipped += 1
        elif entry.is_dir():
            candidates.append(entry)
    evidence: list[ModuleEvidence] = []
    for module in candidates[:max_modules]:
        files, ignored = _safe_files(root, module)
        skipped += ignored
        hashes: dict[str, str] = {}
        for path in files:
            try:
                relative = path.relative_to(root).as_posix()
                hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                skipped += 1
        evidence.append(ModuleEvidence(
            name=module.name, paths=(module.relative_to(root).as_posix(),),
            core_files=tuple(hashes)[:50], file_hashes=hashes,
        ))
    risks = ()
    if len(candidates) > max_modules:
        risks = (f"module limit reached; {len(candidates) - max_modules} modules not indexed",)
    return BootstrapScan(
        profile={"root": str(root), "directory_overview": [item.name for item in candidates[:max_modules]]},
        modules=tuple(item.name for item in evidence), module_evidence=tuple(evidence),
        dependencies={}, risks=risks, skipped_count=skipped,
    )
