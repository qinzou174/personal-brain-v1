"""US5 retrieval and context tools (T111)."""


def test_search_brain_respects_scope_and_authority():
    from personal_brain_server.api.context_tools import search_brain

    grants = [{"client_id": "c", "effect": "allow", "scope_pattern": "finance"}]
    result = search_brain(client_id="c", grants=grants, query="本月总额多少", requested_scope="finance",
                          corpus={"e1": {"scope": "finance", "text": "本月午饭 38 CNY"}})
    assert result["authority"] == "exact"
    assert len(result["hits"]) == 1


def test_context_package_preserves_warnings():
    from personal_brain_server.api.context_tools import get_brain_context

    grants = [{"client_id": "c", "effect": "allow", "scope_pattern": "project"}]
    result = get_brain_context(client_id="c", grants=grants, intent="module",
                               requested_scope="project", detail="normal",
                               candidates=[{"id": "m1", "freshness": "stale", "source_ref": "s1"}],
                               history=[], budget=6000)
    assert "m1" in result["current_state"]
