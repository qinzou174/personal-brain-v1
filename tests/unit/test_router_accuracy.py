"""Router accuracy matrix: expense_total / todo_list positives, negatives, variants, edges.

ER-04: money/time queries must route deterministically; broad keyword substrings
("花了", "total") mis-route non-money queries into the exact path. This matrix
locks the intended boundary.
"""
from __future__ import annotations

import pytest

from personal_brain_domain.retrieval.router import classify_intent


# (text, expected_intent)
POSITIVES = [
    # expense_total — 明确金额/花费意图
    ("本月总额多少", "expense_total"),
    ("我总共花了多少钱", "expense_total"),
    ("去年的总支出是多少", "expense_total"),
    ("上个月总开销", "expense_total"),
    ("这季度费用汇总", "expense_total"),
    ("total expense", "expense_total"),
    ("我的总花费", "expense_total"),
    ("昨天花了500块买书", "expense_total"),
    ("这顿饭花了88元", "expense_total"),
    ("Expense Total", "expense_total"),
    # todo_list — 明确待办意图
    ("我的待办有哪些", "todo_list"),
    ("todo list", "todo_list"),
    ("本周任务清单", "todo_list"),
    ("待办事项", "todo_list"),
]

# (text, intent_that_must_NOT_be_returned)
NEGATIVES = [
    # "花了" 但非钱 → 绝不进 expense_total
    ("我花了多少时间做这件事", "expense_total"),
    ("昨天花了3小时跑步", "expense_total"),
    ("今天花了很多心思准备", "expense_total"),
    # "total" 但非金额 → 绝不进 expense_total
    ("total time spent on project", "expense_total"),
    ("the total headcount is ten", "expense_total"),
    # 无金额关键词的一般问题 → 走混合检索
    ("今天天气怎么样", "expense_total"),
    ("这顿饭一共多少人", "expense_total"),
    ("我的代码哪里有问题", "expense_total"),
    ("开会纪要整理一下", "expense_total"),
]

EDGES = [
    ("", "fuzzy_idea"),
    ("   ", "fuzzy_idea"),
    ("TOTAL", "fuzzy_idea"),  # 孤立的 total 不足以断言是钱
    ("花了", "fuzzy_idea"),  # 孤立的"花了"无金额语境
    ("todo", "todo_list"),
]


@pytest.mark.parametrize("text,expected", POSITIVES)
def test_router_positive(text: str, expected: str) -> None:
    assert classify_intent(text) == expected, f"{text!r} should route to {expected}"


@pytest.mark.parametrize("text,forbidden", NEGATIVES)
def test_router_negative(text: str, forbidden: str) -> None:
    assert classify_intent(text) != forbidden, f"{text!r} must not route to {forbidden}"


@pytest.mark.parametrize("text,expected", EDGES)
def test_router_edge(text: str, expected: str) -> None:
    assert classify_intent(text) == expected, f"edge {text!r} should be {expected}"
