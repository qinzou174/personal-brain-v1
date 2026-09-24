"""US7 bridge bootstrap/sync modules (T087-T089, FR-045/047/048/055)."""

import pytest


def test_bootstrap_excludes_sensitive_dirs_and_hashes_real_files(tmp_path):
    from personal_brain_bridge.bootstrap_scan import excluded, scan_workspace

    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "api.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".env").write_text("SECRET=x", encoding="utf-8")
    assert excluded(".git") and excluded(".env")
    scan = scan_workspace(root_path=str(tmp_path))
    assert ".git" not in scan.modules
    assert "core" in scan.modules
    assert "core/api.py" in scan.module_evidence[0].file_hashes
    assert not any("SECRET" in value for value in scan.module_evidence[0].file_hashes.values())


def test_incremental_sync_invalidates_only_affected_modules():
    from personal_brain_bridge.incremental_sync import map_changes

    change = map_changes(
        changed_paths=("src/api.py", "README.md"),
        module_paths={"api": ("src/api.py",), "docs": ("README.md",), "util": ("src/util.py",)},
        revision="abc", dirty_state=False,
    )
    assert set(change.affected_modules) == {"api", "docs"}
    assert change.revision == "abc"


def test_incremental_sync_matches_descendants_not_only_exact_paths():
    from personal_brain_bridge.incremental_sync import map_changes

    change = map_changes(changed_paths=("apps/api/route.py",), module_paths={"api": ("apps/api",)},
                         revision="def", dirty_state=True)
    assert change.affected_modules == ("api",)


def test_sync_payload_requires_approved_root_proof():
    from personal_brain_bridge.client import build_sync_payload

    with pytest.raises(ValueError):
        build_sync_payload(approved_root="", root_proof="", revision=None, dirty_state=None,
                           changed_paths=(), file_hashes={})
    payload = build_sync_payload(approved_root="/home/kms/workspace", root_proof="proof",
                                 revision="abc", dirty_state=False, changed_paths=("a",), file_hashes={"a": "h"})
    assert payload.root_proof == "proof"
    assert payload.approved_root_identity == "/home/kms/workspace"


def test_capture_workspace_combines_real_git_and_bootstrap(tmp_path):
    import subprocess
    from personal_brain_bridge.client import capture_workspace

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    (tmp_path / "apps").mkdir()
    (tmp_path / "apps" / "main.py").write_text("ok = True", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "apps/main.py"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "initial"], check=True)
    payload = capture_workspace(approved_root=str(tmp_path), bootstrap=True)
    assert payload.revision and payload.branch_ref
    assert payload.modules[0]["name"] == "apps"
    assert len(payload.root_proof) == 64
