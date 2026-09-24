"""US11 Scenario M: trigger, cooldown, merge, non-trigger (T152)."""

import pytest


def test_todo_deadline_triggers_and_priority():
    from personal_brain_domain.operations.notification_triggers import evaluate_trigger

    result = evaluate_trigger(trigger_type="todo_deadline", risk="high")
    assert result.notify is True
    assert result.priority == "high"


def test_repeated_failure_merged_within_cooldown():
    from personal_brain_domain.operations.notification_policy import decide_send

    # First occurrence: no recent send -> eligible.
    eligible = decide_send(dedupe_key="index-failure", last_sent_minutes_ago=120, cooldown_minutes=60)
    assert eligible.send is True
    # Repeated within the 60-minute cooldown -> merged/suppressed.
    within = decide_send(dedupe_key="index-failure", last_sent_minutes_ago=55, cooldown_minutes=60)
    assert within.send is False  # merged/suppressed within cooldown
    recent = decide_send(dedupe_key="index-failure", last_sent_minutes_ago=5, cooldown_minutes=60)
    assert recent.send is False  # within merge window, no duplicate


def test_trend_does_not_notify_by_default():
    from personal_brain_domain.operations.notification_triggers import evaluate_trigger

    result = evaluate_trigger(trigger_type="preference_trend", risk="low")
    assert result.notify is False
