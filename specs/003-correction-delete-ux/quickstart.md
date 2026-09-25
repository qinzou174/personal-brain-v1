# Quickstart 验证指南：003-correction-delete-ux

前置：生产/本地实例运行中，prod-trial 凭据可用；全量 pytest 通过。

## 1. 笔记更正（US1）

1. `save_note(content="SIMTEST-更正演练 旧内容", ...)` → 记录 record_id
2. `update_note(old_note_id=record_id, content="SIMTEST-更正演练 新内容", ...)` → 响应含新 record_id + superseded_id=旧 id + index_state=pending
3. `search_brain("旧内容")` → 0 命中；`search_brain("新内容")` → 命中新条目
4. `get_entry_content(新 entry_id)` → 全文为新内容

## 2. 待办删除（US2）

1. `add_todo("SIMTEST-待删待办")` → todo_id
2. `delete_todo(todo_id, expected_version=1)` → accepted
3. `list_todos` → 无该条；重复删除 → NOT_FOUND

## 3. 账目更正（US3）

1. `add_expense(amount=99.00)` → expense_id
2. `correct_expense(expense_id, new_amount=9.90)` → 新 expense_id + corrected_from
3. `get_expense_summary` → 汇总反映 9.90，旧 99 不计
4. `correct_expense(new_amount=0)` → in-band VALIDATION_FAILED

## 4. 索引提示（US4）

任意写入响应包含 `"index_state": "pending"`。

## 5. 时间范围检索（US5）

1. 写两条笔记（内容含不同日期语境，写入时间不同日更有说服力——可回填验证）
2. `search_brain(query=..., time_from=..., time_to=...)` → 只返回范围内条目
3. 部署后执行一次 `rebuild-index` 管理命令回填历史卡片的 content_time

## 6. 实时冲突提示（US6）

1. `propose_self_claim(A, "我喜欢X")` → 正常
2. `propose_self_claim(A, "我不喜欢X")` → 响应含 `conflict_warning`

## 7. 项目删除自授权（US7）

1. 新客户端 `create_project` → `create_deletion_plan([["project", id]], requested_scope="projects")`
2. 期望不再 SCOPE_DENIED（旧版本必现）

## 8. 其余（US8/9/10/11）

- 路由矩阵：`有什么要做的事`@todo → exact；`最近买了什么`@finance → exact
- 同名项目：建同名 → 响应含 duplicate_name_hint
- A 类主张：提交后 get_self_context 显示 lifecycle_state=active
- 已裁决语义：对 approved 项再次 resolve → ALREADY_RESOLVED
