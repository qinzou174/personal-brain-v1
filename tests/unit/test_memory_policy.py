"""Red-first A/B/C and evidence edge cases from ER-01/02/06."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest


def signals(*, count=3, span_days=14, contexts=2, direct=True, contradiction=False, same_source=False):
    from personal_brain_domain.memory.evidence import PromotionEvidence

    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    common_source = uuid4()
    values = []
    for index in range(count):
        values.append(PromotionEvidence(
            source_id=common_source if same_source else uuid4(),
            observed_at=start + timedelta(days=span_days if index == count - 1 else 0),
            context=f"context-{index % contexts}",
            direct_user_statement=direct and index == 0,
            contradicts=contradiction and index == count - 1,
        ))
    return values


@pytest.mark.parametrize("kwargs", [
    {"count": 2},
    {"span_days": 13},
    {"contexts": 1},
    {"direct": False},
    {"contradiction": True},
])
def test_b_preference_not_established_when_any_threshold_is_missing(kwargs):
    from personal_brain_domain.memory.evidence import assess_b_promotion

    assert assess_b_promotion(signals(**kwargs)) != "established"


def test_b_preference_established_at_all_inclusive_thresholds():
    from personal_brain_domain.memory.evidence import assess_b_promotion

    assert assess_b_promotion(signals()) == "established"


def test_reprocessing_one_canonical_source_does_not_multiply_evidence():
    from personal_brain_domain.memory.evidence import assess_b_promotion

    assert assess_b_promotion(signals(same_source=True)) != "established"


@pytest.mark.parametrize("confirmed,allowed", [(False, False), (True, True)])
def test_class_c_activation_requires_owner_confirmation(confirmed, allowed):
    from personal_brain_domain.memory.self_model_policy import can_activate

    assert can_activate(policy_class="C", owner_confirmed=confirmed, source_kind="explicit_user_statement") is allowed


def test_imported_or_model_text_never_counts_as_owner_confirmation():
    from personal_brain_domain.memory.self_model_policy import can_activate

    for kind in ("original_document", "ai_inference", "ai_extraction"):
        assert not can_activate(policy_class="C", owner_confirmed=False, source_kind=kind)


@pytest.mark.parametrize("age_days,expected", [(89, "candidate"), (90, "candidate"), (91, "expired"), (179, "established"), (180, "established"), (181, "historical")])
def test_b_candidate_and_established_age_boundaries(age_days, expected):
    from personal_brain_domain.memory.lifecycle import retention_transition

    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    current = "candidate" if age_days <= 91 else "established"
    assert retention_transition(current, last_supported_at=now - timedelta(days=age_days), now=now) == expected


def test_temporary_memory_without_expiry_is_rejected():
    from personal_brain_domain.memory.lifecycle import validate_memory_lifecycle

    with pytest.raises(ValueError):
        validate_memory_lifecycle(state="temporary", expires_at=None)


def test_explicit_a_memory_does_not_age_into_unconfirmed_expiry():
    from personal_brain_domain.memory.lifecycle import retention_transition

    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert retention_transition("active", policy_class="A", last_supported_at=now - timedelta(days=1_000), now=now) == "active"


def test_an_experience_alone_does_not_establish_global_preference():
    from personal_brain_domain.memory.evidence import experience_to_self_candidate

    outcome = experience_to_self_candidate(source_id=uuid4(), expression="I enjoyed this once", context="one concert")
    assert outcome.establishment == "candidate"
    assert outcome.source_ids


def test_last_live_source_removal_orphans_derived_content():
    from personal_brain_domain.intake.lineage import recalculate_derivation_state

    assert recalculate_derivation_state(current_state="active", live_source_ids=[]) == "orphaned"
    assert recalculate_derivation_state(current_state="active", live_source_ids=[uuid4()]) == "recomputing"


def test_derived_access_is_intersection_with_maximum_source_sensitivity():
    from personal_brain_domain.intake.lineage import derive_access_boundary

    result = derive_access_boundary([
        {"scopes": {"personal", "project:a"}, "sensitivity": "personal"},
        {"scopes": {"personal", "finance"}, "sensitivity": "private"},
    ])
    assert result.scopes == {"personal"}
    assert result.sensitivity == "private"


def test_intake_priority_applies_security_then_c_before_explicit_remember():
    from personal_brain_domain.intake.service import decide_intake

    denied = decide_intake(authorized=False, secret_match=False, high_impact=True, explicit_remember=True, ordinary_signal=True)
    assert denied.action == "reject"
    secret = decide_intake(authorized=True, secret_match=True, high_impact=True, explicit_remember=True, ordinary_signal=True)
    assert secret.action == "reject"
    high_impact = decide_intake(authorized=True, secret_match=False, high_impact=True, explicit_remember=True, ordinary_signal=True)
    assert high_impact.action == "pending_confirmation"
    explicit = decide_intake(authorized=True, secret_match=False, high_impact=False, explicit_remember=True, ordinary_signal=True)
    assert explicit.policy_class == "A"
    ordinary = decide_intake(authorized=True, secret_match=False, high_impact=False, explicit_remember=False, ordinary_signal=True)
    assert ordinary.policy_class == "B" and ordinary.establishment == "candidate"
    low_value = decide_intake(authorized=True, secret_match=False, high_impact=False, explicit_remember=False, ordinary_signal=False)
    assert low_value.level == "L0"
