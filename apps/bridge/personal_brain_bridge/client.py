"""Bridge-to-Brain sync contract and approved-root proof.

FR-047/FR-055/FR-098: the bridge submits only approved-root evidence; every sync
carries a root proof and bounded change data.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from personal_brain_bridge.bootstrap_scan import scan_workspace
from personal_brain_bridge.git_observer import observe_repository
from personal_brain_bridge.workspace_boundary import normalize_root
from pathlib import Path


@dataclass(frozen=True)
class SyncPayload:
    # Field names mirror the server-side ``sync_workspace`` schema exactly, so a
    # bridge payload can be sent as-is (they used to drift: `approved_root` vs
    # `approved_root_identity`).
    approved_root_identity: str
    root_proof: str
    revision: str | None
    branch_ref: str | None
    dirty_state: bool | None
    changed_paths: tuple[str, ...]
    file_hashes: dict[str, str]
    modules: tuple[dict, ...] = ()
    bridge_client_id: str | None = None
    idempotency_key: str | None = None


def build_sync_payload(*, approved_root: str, root_proof: str, revision: str | None,
                       dirty_state: bool | None, changed_paths: tuple[str, ...],
                       file_hashes: dict[str, str], branch_ref: str | None = None,
                       modules: tuple[dict, ...] = (), bridge_client_id: str | None = None,
                       idempotency_key: str | None = None) -> SyncPayload:
    if not approved_root or not root_proof:
        raise ValueError("sync requires approved root and proof")
    if len(changed_paths) > 1000:
        raise ValueError("changed paths exceed bound")
    return SyncPayload(approved_root_identity=approved_root, root_proof=root_proof,
                       revision=revision, branch_ref=branch_ref, dirty_state=dirty_state,
                       changed_paths=changed_paths, file_hashes=dict(file_hashes),
                       modules=tuple(modules), bridge_client_id=bridge_client_id,
                       idempotency_key=idempotency_key)


def capture_workspace(*, approved_root: str, since_revision: str | None = None,
                      bootstrap: bool = False) -> SyncPayload:
    """Capture a real bounded workspace observation suitable for ``sync_workspace``."""
    root = normalize_root(Path(approved_root))
    identity = str(root)
    evidence = observe_repository(root, since_revision=since_revision)
    if not evidence.available:
        raise ValueError("approved workspace is not an observable Git repository root")
    modules: tuple[dict, ...] = ()
    if bootstrap:
        scan = scan_workspace(root_path=identity)
        modules = tuple({
            "name": item.name, "paths": list(item.paths), "core_files": list(item.core_files),
            "file_hashes": dict(item.file_hashes), "dependencies": list(scan.dependencies.get(item.name, ())),
        } for item in scan.module_evidence)
    return build_sync_payload(
        approved_root=identity,
        root_proof=hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        revision=evidence.revision, branch_ref=evidence.branch, dirty_state=evidence.dirty,
        changed_paths=evidence.changed_paths, file_hashes=evidence.file_hashes, modules=modules,
    )
