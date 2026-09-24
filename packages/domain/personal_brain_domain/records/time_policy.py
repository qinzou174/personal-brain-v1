"""Relative-time resolution and record-time admission.

ER-04: relative dayparts resolve to windows, never invented point times; missing
or ambiguous timezone/DST evidence routes to review instead of guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class DaypartResolution:
    state: str
    window_start: datetime | None = None
    window_end: datetime | None = None
    precision: str | None = None
    raw_text: str | None = None
    capture_time: datetime | None = None


def _aware(value: datetime, timezone_name: str | None) -> datetime:
    if value.tzinfo is not None and value.utcoffset() is not None:
        return value
    if not timezone_name:
        raise ValueError("relative time requires a capture timezone")
    zone = ZoneInfo(timezone_name)
    # A naive wall-clock time that maps to two instants (DST fall-back) is
    # ambiguous: the two possible localizations differ, so route to review.
    if value.replace(tzinfo=zone, fold=0).timestamp() != value.replace(tzinfo=zone, fold=1).timestamp():
        raise ValueError("ambiguous capture time")
    return value.replace(tzinfo=zone)


def resolve_relative_daypart(expression: str, *, capture_time: datetime, owner_timezone: str | None):
    """Tomorrow-afternoon style windows; pending_review when evidence is missing.

    With an owner timezone the capture time is localized and the window is a real
    interval (12:00-18:00 for 下午); ambiguous DST falls back to review.
    """
    if "下午" in expression and "明天" in expression:
        try:
            capture = _aware(capture_time, owner_timezone)
            start_day = capture.date() + timedelta(days=1)
            window_start = datetime.combine(start_day, datetime.min.time().replace(hour=12, minute=0), tzinfo=capture.tzinfo)
            window_end = datetime.combine(start_day, datetime.min.time().replace(hour=18, minute=0), tzinfo=capture.tzinfo)
            return DaypartResolution(state="accepted", window_start=window_start, window_end=window_end,
                                     precision="window", raw_text=expression, capture_time=capture)
        except Exception:
            return DaypartResolution(state="pending_review", raw_text=expression, capture_time=capture_time)
    return DaypartResolution(state="pending_review", raw_text=expression, capture_time=capture_time)


def admit_record_time(*, occurred_at, raw_text, capture_time, owner_timezone):
    """Record time must come from an occurrence or raw capture evidence."""
    if occurred_at is None and raw_text is None and capture_time is None:
        raise ValueError("record time requires occurrence or raw capture evidence")
    return DaypartResolution(state="accepted", window_start=occurred_at, precision="point",
                             raw_text=raw_text, capture_time=capture_time)


def present_event_in_timezone(original: datetime, timezone_name: str):
    """Display without rewriting the original instant."""
    return original.astimezone(ZoneInfo(timezone_name))
