"""Project tools application operations (T081, FR-041..053/FR-099)."""


def test_fresh_client_recovers_active_task_with_checkpoints():
    from personal_brain_server.api.project_tools import (
        checkpoint_task, get_recovery, register_project, reset_store, start_task,
    )

    reset_store()
    register_project(project_id="proj-1", name="P", purpose="平台")
    grants = [{"client_id": "c", "effect": "allow", "tool_pattern": "project.write", "project": "proj-1"},
              {"client_id": "c", "effect": "allow", "tool_pattern": "project.read", "project": "proj-1"}]
    task = start_task(client_id="c", grants=grants, project_id="proj-1", goal="完成任务",
                      revision="abc", dirty_state=False)
    checkpoint_task(client_id="c", grants=grants, project_id="proj-1", task_id=task["task_id"],
                    completed_work="实现", next_step="做验收")
    recovered = get_recovery(client_id="c", grants=grants, project_id="proj-1")
    assert recovered["active_task"]["goal"] == "完成任务"
    assert recovered["next_step"] == "做验收"


def test_project_scope_denied_for_other_project():
    from personal_brain_server.api.project_tools import get_recovery, register_project, reset_store

    from personal_brain_domain.common.errors import BrainError

    reset_store()
    register_project(project_id="proj-a", name="A", purpose="x")
    grants = [{"client_id": "c", "effect": "allow", "tool_pattern": "project.read", "project": "proj-a"}]
    try:
        get_recovery(client_id="c", grants=grants, project_id="proj-b")
    except BrainError as caught:
        assert caught.code in {"SCOPE_DENIED", "TOOL_DENIED"}
    else:
        raise AssertionError("project read must be denied outside grant scope")