"""Tool registry contract (T054, FR-002/098/099)."""


def test_registry_exposes_replaceable_life_record_tools():
    from personal_brain_server.protocols.tools import list_tool_names, resolve_tool

    names = list_tool_names()
    for expected in ("save_note", "add_expense", "get_expense_summary", "add_todo", "list_todos", "complete_todo"):
        assert expected in names
    assert callable(resolve_tool("add_expense"))


def test_registry_rejects_unknown_tools_without_policy():
    from personal_brain_server.protocols.tools import resolve_tool

    try:
        resolve_tool("delete_all")
    except KeyError:
        pass
    else:
        raise AssertionError("unknown tool must not resolve")
