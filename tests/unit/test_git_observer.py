"""Bounded Git revision/status/change/hash observation (T035, FR-047/048/054/055)."""

import subprocess
import pytest


def test_git_revision_and_dirty_state_observed_bounded():
    from personal_brain_bridge.git_observer import observe_repository

    state = observe_repository("/nonexistent/repo/path")
    assert state.revision is None
    assert state.dirty is None
    assert state.branch is None
    assert state.available is False


def test_dirty_evidence_is_value_bounded():
    from personal_brain_bridge.git_observer import ChangeEvidence

    evidence = ChangeEvidence(revision="abc", branch="main", dirty=False, changed_paths=(), file_hashes={})
    encoded = repr(evidence)
    assert "abc" in encoded
    assert len(evidence.changed_paths) <= 1000


def test_real_repository_reports_revision_dirty_path_and_hash(tmp_path):
    from personal_brain_bridge.git_observer import observe_repository

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("one", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "initial"], check=True)
    baseline = observe_repository(tmp_path)
    tracked.write_text("two", encoding="utf-8")
    evidence = observe_repository(tmp_path, since_revision=baseline.revision)
    assert evidence.available and evidence.revision == baseline.revision
    assert evidence.dirty is True and evidence.changed_paths == ("tracked.txt",)
    assert len(evidence.file_hashes["tracked.txt"]) == 64
