"""US3 Scenario C: A/B/C policy, contradiction and evidence-removal (T063)."""

from datetime import datetime, timedelta, timezone

import pytest


def test_class_a_active_explicit_rule():
    from personal_brain_domain.memory.self_model_policy import classify_and_activate

    result = classify_and_activate(text="记住，以后项目时间统一北京时间", explicit_remember=True,
                                   high_impact=False, owner_confirmed=False)
    assert result.policy_class == "A"
    assert result.lifecycle == "active"
    assert result.establishment == "explicit"


def test_class_b_candidate_not_established():
    from personal_brain_domain.memory.self_model_policy import classify_and_activate

    result = classify_and_activate(text="最近挺喜欢爵士乐", explicit_remember=False,
                                   high_impact=False, owner_confirmed=False)
    assert result.policy_class == "B"
    assert result.lifecycle == "candidate"
    assert result.establishment == "candidate"


def test_class_c_pending_confirmation_not_active():
    from personal_brain_domain.memory.self_model_policy import classify_and_activate

    result = classify_and_activate(text="我的核心人生哲学已改变为 X", explicit_remember=True,
                                   high_impact=True, owner_confirmed=False)
    assert result.policy_class == "C"
    assert result.lifecycle == "pending_confirmation"
    assert result.establishment == "candidate"


def test_explicit_contradiction_supersedes_inference():
    from personal_brain_domain.memory.history import apply_contradiction

    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    result = apply_contradiction(
        current_statement="用户可能不喜欢京都",
        new_statement="其实我很喜欢京都",
        current_kind="inference",
        new_kind="explicit_user_statement",
        now=now,
    )
    assert result.current_state == "superseded"
    assert result.history_retained is True
    assert result.current_is_historical is True


def test_evidence_removal_recalculates_confidence_without_deleting_claim():
    from personal_brain_domain.memory.evidence import recalculate_on_evidence_loss

    result = recalculate_on_evidence_loss(evidence_ids=("e1", "e2"), removed_evidence_id="e1")
    assert "e1" not in result.remaining_evidence
    assert result.recalculation_triggered is True
    assert result.claim_preserved is True
