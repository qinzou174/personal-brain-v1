# MCP 工具契约变更：003-correction-delete-ux

工具面 34 → 37。全部新工具复用既有域权限；响应增字段不破坏既有键。

## update_note（knowledge.write）

```json
// 输入
{"old_note_id": "<uuid>", "content": "更正后的内容", "requested_scope": "knowledge", "idempotency_key": "<uuid>"}
// 成功输出
{"status": "accepted", "persistence": "canonical_committed", "record_id": "<新uuid>",
 "superseded_id": "<旧uuid>", "source_id": "<uuid>", "operation_id": "<uuid>", "index_state": "pending"}
// 错误
NOT_FOUND（旧条目不存在/已删）；VALIDATION_FAILED（空内容）
```

## delete_todo（todo.write）

```json
// 输入
{"todo_id": "<uuid>", "expected_version": 1, "requested_scope": "todo", "idempotency_key": "<uuid>"}
// 成功输出
{"status": "accepted", "persistence": "canonical_committed", "todo_id": "<uuid>", "state": "deleted", "index_state": "pending"}
// 错误
NOT_FOUND（不存在）；VERSION_CONFLICT（版本不符）
```

## correct_expense（finance.write）

```json
// 输入
{"expense_id": "<uuid>", "new_amount": "9.90", "requested_scope": "finance", "idempotency_key": "<uuid>"}
// 成功输出
{"status": "accepted", "persistence": "canonical_committed", "expense_id": "<新uuid>",
 "corrected_from": "<旧uuid>", "index_state": "pending"}
// 错误
NOT_FOUND；VALIDATION_FAILED（金额非法/非数字）
```

## 既有工具响应增字段

| 工具 | 新字段 | 语义 |
|---|---|---|
| save_note / add_todo / add_expense / propose_self_claim 等 | `index_state: "pending"` | 检索卡异步建立，约数秒后可搜 |
| search_brain / search_project / get_brain_context | 输入可选 `time_from`/`time_to`（ISO 日期） | 按内容记录时间过滤；无时间戳卡片在给定时排除 |
| create_project | 可选 `duplicate_name_hint: [{project_id, name}]` | 同名存活项目提示，不阻止 |
| propose_self_claim | 可选 `conflict_warning: {claim_id, claim}` | 同类别极性相反的既有主张提示，不阻止 |

## 错误码

- 新增稳定码 `ALREADY_RESOLVED`："该审核项已完成裁决"——对非 open 项的 resolve 返回（替代含混的 CONFIRMATION_REQUIRED）
