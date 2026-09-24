"""Red-first exact money and relative-time boundaries from ER-04."""

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest


@pytest.mark.parametrize("amount", ["0.0000", "-0.0001", "1.00001", "10000000000000000.0000"])
def test_amount_rejects_zero_negative_excess_scale_or_precision(amount):
    from personal_brain_domain.records.expenses import validate_money

    with pytest.raises(ValueError):
        validate_money(Decimal(amount), currency="CNY", kind="expense")


@pytest.mark.parametrize("amount", [Decimal("NaN"), Decimal("Infinity"), 0.1])
def test_non_finite_or_binary_float_money_is_rejected(amount):
    from personal_brain_domain.records.expenses import validate_money

    with pytest.raises((TypeError, ValueError)):
        validate_money(amount, currency="CNY", kind="expense")


@pytest.mark.parametrize("amount", ["0.0001", "1.0000", "9999999999999999.9999"])
def test_amount_accepts_numeric_20_4_positive_edges(amount):
    from personal_brain_domain.records.expenses import validate_money

    assert validate_money(Decimal(amount), currency="CNY", kind="expense").amount == Decimal(amount)


@pytest.mark.parametrize("currency", ["", "CN", "CNYX", "cny", None])
def test_currency_must_be_explicit_three_letter_code(currency):
    from personal_brain_domain.records.expenses import validate_money

    with pytest.raises(ValueError):
        validate_money(Decimal("1.0000"), currency=currency, kind="expense")


def test_missing_currency_routes_to_review_unless_owner_default_is_configured():
    from personal_brain_domain.records.expenses import admit_expense

    undecided = admit_expense(Decimal("38.0000"), currency=None, owner_default_currency=None)
    assert undecided.state == "pending_review"
    accepted = admit_expense(Decimal("38.0000"), currency=None, owner_default_currency="CNY")
    assert accepted.currency == "CNY"
    assert accepted.used_owner_default is True


def test_refund_is_positive_typed_and_net_subtracts_without_cross_currency_sum():
    from personal_brain_domain.records.expenses import aggregate_net_by_currency, validate_money

    entries = [
        validate_money(Decimal("38.0000"), currency="CNY", kind="expense"),
        validate_money(Decimal("8.0000"), currency="CNY", kind="refund"),
        validate_money(Decimal("5.0000"), currency="USD", kind="expense"),
    ]
    assert aggregate_net_by_currency(entries) == {"CNY": Decimal("30.0000"), "USD": Decimal("5.0000")}


def test_expense_adjustment_keeps_prior_version_and_requires_expected_version():
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_domain.records.expenses import correct_expense

    original = {"amount": Decimal("38.0000"), "currency": "CNY", "version": 1}
    with pytest.raises(BrainError) as caught:
        correct_expense(original, new_amount=Decimal("39.0000"), expected_version=0)
    assert caught.value.code == "VERSION_CONFLICT"
    corrected = correct_expense(original, new_amount=Decimal("39.0000"), expected_version=1)
    assert corrected.amount == Decimal("39.0000")
    assert corrected.version == 2
    assert corrected.previous.amount == Decimal("38.0000")
    assert original["amount"] == Decimal("38.0000")


def test_tomorrow_afternoon_preserves_window_not_invented_point_time():
    from personal_brain_domain.records.time_policy import resolve_relative_daypart

    capture = datetime(2026, 9, 23, 23, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    result = resolve_relative_daypart("明天下午", capture_time=capture, owner_timezone="Asia/Shanghai")
    assert result.window_start == datetime(2026, 9, 24, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert result.window_end == datetime(2026, 9, 24, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert result.precision == "window"
    assert not hasattr(result, "fabricated_exact_time")


def test_relative_time_without_capture_timezone_requires_review():
    from personal_brain_domain.records.time_policy import resolve_relative_daypart

    result = resolve_relative_daypart("明天下午", capture_time=datetime(2026, 9, 23, 23, 30), owner_timezone=None)
    assert result.state == "pending_review"
    assert result.window_start is None


def test_record_time_requires_occurrence_or_raw_capture_evidence():
    from personal_brain_domain.records.time_policy import admit_record_time

    with pytest.raises(ValueError):
        admit_record_time(occurred_at=None, raw_text=None, capture_time=None, owner_timezone="Asia/Shanghai")
    admitted = admit_record_time(occurred_at=None, raw_text="昨天吃饭", capture_time=datetime(2026, 9, 23, tzinfo=ZoneInfo("Asia/Shanghai")), owner_timezone="Asia/Shanghai")
    assert admitted.raw_text == "昨天吃饭"
    assert admitted.capture_time is not None


def test_ambiguous_daylight_saving_capture_time_requires_review():
    from personal_brain_domain.records.time_policy import resolve_relative_daypart

    result = resolve_relative_daypart("明天下午", capture_time=datetime(2026, 11, 1, 1, 30), owner_timezone="America/New_York")
    assert result.state == "pending_review"


def test_timezone_change_does_not_rewrite_original_event_instant():
    from personal_brain_domain.records.time_policy import present_event_in_timezone

    original = datetime(2026, 9, 23, 15, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    displayed = present_event_in_timezone(original, "UTC")
    assert displayed.utcoffset() == timedelta(0)
    assert displayed.timestamp() == original.timestamp()
    assert original.tzinfo == ZoneInfo("Asia/Shanghai")


@pytest.mark.parametrize("from_state", ["pending", "in_progress"])
def test_todo_can_complete_from_both_active_states(from_state):
    from personal_brain_domain.records.todos import transition_todo

    changed = transition_todo(state=from_state, target_state="completed", version=3, expected_version=3)
    assert changed.state == "completed"
    assert changed.version == 4


def test_todo_version_conflict_preserves_prior_state():
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_domain.records.todos import transition_todo

    with pytest.raises(BrainError) as caught:
        transition_todo(state="pending", target_state="completed", version=3, expected_version=2)
    assert caught.value.code == "VERSION_CONFLICT"


def test_terminal_todo_cannot_reopen_without_correction_event():
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_domain.records.todos import transition_todo

    with pytest.raises(BrainError):
        transition_todo(state="completed", target_state="pending", version=3, expected_version=3)


def test_terminal_todo_reopen_is_versioned_correction_not_history_erasure():
    from personal_brain_domain.records.todos import correct_terminal_todo

    corrected = correct_terminal_todo(state="completed", target_state="pending", version=3, expected_version=3, reason="entered in error")
    assert corrected.state == "pending"
    assert corrected.version == 4
    assert corrected.previous_state == "completed"
    assert corrected.correction_reason == "entered in error"


def test_event_parent_cycle_and_cross_owner_relation_are_rejected():
    from uuid import uuid4

    from personal_brain_domain.records.events import validate_parent_chain
    from personal_brain_domain.records.relations import validate_relation_owners

    event_id, parent_id = uuid4(), uuid4()
    with pytest.raises(ValueError):
        validate_parent_chain(event_id=event_id, parent_id=parent_id, ancestor_ids=[event_id])
    with pytest.raises(ValueError):
        validate_relation_owners(subject_owner_id=uuid4(), object_owner_id=uuid4())
