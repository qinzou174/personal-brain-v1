"""Context recovery under removed chat history and replaced identity (T165)."""

from __future__ import annotations


def test_recovery_with_replaced_client_identity():
    from personal_brain_domain.projects.recovery import assemble_recovery_package

    package = assemble_recovery_package(
        project={"purpose": "keep momentum"},
        active_task={"goal": "finish v1", "remaining_work": ["acceptance"]},
        checkpoints=(),
        relevant_modules={"core": "stale"},
        recent_changes=(),
        revision_evidence={"revision": "r1", "dirty": True},
        now=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    assert package["active_task"]["goal"] == "finish v1"
    assert package["revision"] == "r1"


def test_no_chat_history_never_fabricates_context():
    from personal_brain_domain.projects.recovery import assemble_recovery_package

    package = assemble_recovery_package(project={"purpose": "x"}, active_task=None, checkpoints=(),
                                        relevant_modules={}, recent_changes=(),
                                        revision_evidence={}, now=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
    assert package["active_task"] is None
    assert package["next_step"]  # honest instruction to inspect sources
