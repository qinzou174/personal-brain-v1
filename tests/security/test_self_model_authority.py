"""US3 authority: inference cannot outrank explicit statements (T064)."""

import pytest


def test_inference_never_outranks_explicit_statement():
    from personal_brain_domain.memory.history import resolve_authority

    resolved = resolve_authority(
        candidate_a={"kind": "inference", "confidence": 0.99, "statement": "喜欢咖啡"},
        candidate_b={"kind": "explicit_user_statement", "confidence": 0.5, "statement": "不喜欢咖啡"},
    )
    assert resolved.winner == "explicit_user_statement"
    assert resolved.confidence_did_not_decide is True


def test_explicit_outranks_contradictory_inference_but_prior_remains_historical():
    from personal_brain_domain.memory.history import apply_contradiction

    now = datetime_utc()
    result = apply_contradiction(
        current_statement="喜欢爵士乐", new_statement="其实不喜欢爵士乐",
        current_kind="inference", new_kind="explicit_user_statement", now=now,
    )
    assert result.current_state == "superseded"
    assert result.current_is_historical is True


def datetime_utc():
    from datetime import datetime, timezone

    return datetime(2026, 9, 1, tzinfo=timezone.utc)
