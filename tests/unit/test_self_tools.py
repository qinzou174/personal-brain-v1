"""Self-model confirmation operations (T070, FR-026/FR-076)."""

import pytest


def test_class_c_proposal_needs_confirmation_before_active():
    from personal_brain_server.api.self_tools import InMemorySelfTools

    tools = InMemorySelfTools()
    claim = tools.propose(category="value", claim="人生哲学已改变", policy_class="C")
    assert claim.lifecycle == "pending_confirmation"
    with pytest.raises(Exception):
        tools.approve(claim_id=claim.claim_id, version=0)  # wrong version
    approved = tools.approve(claim_id=claim.claim_id, version=1)
    assert approved.lifecycle == "active"


def test_class_b_candidate_requires_no_confirmation():
    from personal_brain_server.api.self_tools import InMemorySelfTools

    tools = InMemorySelfTools()
    claim = tools.propose(category="interest", claim="喜欢爵士乐", policy_class="B")
    assert claim.lifecycle == "candidate"
    with pytest.raises(Exception):
        tools.approve(claim_id=claim.claim_id, version=1)
