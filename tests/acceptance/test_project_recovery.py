"""US4 Scenario E: project-task recovery and freshness (T072)."""

from datetime import datetime, timezone

import pytest


def test_fresh_client_recovery_assembles_project_context():
    from personal_brain_domain.projects.recovery import assemble_recovery_package

    now = datetime(2026, 9, 23, tzinfo=timezone.utc)
    package = assemble_recovery_package(
        project={"name": "Personal Brain", "purpose": "private memory"},
        active_task={"id": "task-1", "goal": "完成项目", "remaining_work": ["验收"]},
        checkpoints=(("cp-1", "开始"), ("cp-2", "实现完成")),
        relevant_modules={"brain-core": "fresh"},
        recent_changes=(("c-1", "新增核心模块"),),
        revision_evidence={"revision": "abc", "dirty": False},
        now=now,
    )
    assert package["active_task"]["goal"] == "完成项目"
    assert package["next_step"] is not None
    assert "brain-core" in package["relevant_modules"]


def test_unknown_freshness_never_pretends_fresh():
    from personal_brain_domain.projects.modules import freshness_for

    assert freshness_for(evidence=None) == "unknown"
    assert freshness_for(evidence={}) == "unknown"
    assert freshness_for(evidence={"fresh": True}) == "fresh"
    assert freshness_for(evidence={"fresh": False}) == "stale"
