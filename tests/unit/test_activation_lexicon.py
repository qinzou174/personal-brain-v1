"""Pure-function contracts for the backend-activation helpers (no database)."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest


def test_negation_only_changes_polarity_not_the_topic_signature():
    from personal_brain_worker.evolution import is_negative, topic_key

    assert topic_key("喜欢喝咖啡") == topic_key("不喜欢喝咖啡")
    assert topic_key("不 喜欢，喝咖啡。") == topic_key("喜欢喝咖啡")
    assert is_negative("喜欢喝咖啡") is False
    assert is_negative("不喜欢喝咖啡") is True
    assert is_negative("我再也不喝咖啡了") is True


def test_different_topics_do_not_collide():
    from personal_brain_worker.evolution import topic_key

    assert topic_key("喜欢喝咖啡") != topic_key("喜欢喝奶茶")
    assert topic_key("") == ""


def test_parse_extraction_output_accepts_json_inside_prose_and_aliases():
    from personal_brain_worker.extraction import parse_extraction_output

    text = (
        "这是抽取结果：\n```json\n"
        '{"summary": "用户喜欢喝咖啡", "candidates": ['
        '{"category": "偏好", "claim": "用户喜欢喝咖啡", "confidence": "high", "quote": "最近爱喝拿铁"},'
        '{"category": "not-a-category", "claim": "非法类别"}]}\n```'
    )
    parsed = parse_extraction_output(text)

    assert parsed["summary"] == "用户喜欢喝咖啡"
    assert len(parsed["candidates"]) == 1
    candidate = parsed["candidates"][0]
    assert candidate["category"] == "preference"
    assert candidate["claim"] == "用户喜欢喝咖啡"
    assert candidate["confidence"] == "high"
    assert parsed["dropped"] == 1


def test_parse_extraction_output_rejects_output_without_usable_json():
    from personal_brain_worker.extraction import parse_extraction_output

    for text in ("抱歉，我无法输出。", '{"candidates": []}', '{"summary": ""}', ""):
        with pytest.raises(ValueError):
            parse_extraction_output(text)


def test_day_window_uses_the_configured_local_timezone():
    from personal_brain_worker.llm_budget import day_window

    start, end = day_window(datetime(2026, 9, 24, 20, 0, tzinfo=timezone.utc), "Asia/Shanghai")

    assert start == datetime(2026, 9, 24, 16, 0, tzinfo=timezone.utc)  # 2026-09-25 00:00 +08
    assert end == datetime(2026, 9, 25, 16, 0, tzinfo=timezone.utc)
    assert (end - start).total_seconds() == 86400


def test_schedule_due_and_bucket_helpers():
    from personal_brain_worker.scheduler import DailySchedule, schedule_bucket, schedule_due

    schedule = DailySchedule(job_type="daily_digest", hour=3, minute=10)
    local = ZoneInfo("Asia/Shanghai")

    assert schedule_due(schedule, local_now=datetime(2026, 9, 25, 3, 9, tzinfo=local)) is False
    assert schedule_due(schedule, local_now=datetime(2026, 9, 25, 3, 10, tzinfo=local)) is True
    assert schedule_due(schedule, local_now=datetime(2026, 9, 25, 23, 59, tzinfo=local)) is True
    assert schedule_bucket(local_now=datetime(2026, 9, 25, 23, 59, tzinfo=local)) == "2026-09-25"