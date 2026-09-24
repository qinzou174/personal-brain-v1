# FEATURE_MATRIX — 功能覆盖矩阵（第 0 轮盘点）

> 每轮更新。覆盖状态：`PASS | FAIL | BLOCKED | N/A`；BLOCKED 必须写原因与解除条件。
> 2026-09-24 建立：30 个 MCP 工具 + CLI 生命周期 + 健康端点。沙箱 worktree 已建（qa/loop-testing）。

| 功能 | 入口 | 角色 | 场景 | 覆盖状态 | 最近轮次 | 关联 ISSUE | 证据位置 |
|------|------|------|------|----------|----------|-----------|----------|
| save_note | MCP tools/call | 小白/老手 | 正常/幂等重放/空content | PASS | R1 | ISSUE-LT-003(已修) | runs/round-1.md |
| add_expense | MCP tools/call | 小白 | 正常/多币种/空category | PASS | R1 | — | runs/round-1.md |
| add_todo | MCP tools/call | 小白 | 正常/priority/空content | PASS | R1 | ISSUE-LT-003(已修) | runs/round-1.md |
| complete_todo | MCP tools/call | 老手 | 正常/非法id/版本 | PASS | R1 | — | runs/round-1.md |
| list_todos | MCP tools/call | 小白 | 正常/空列表 | PASS | R1 | — | runs/round-1.md |
| search_brain | MCP tools/call | 老手 | 正常/中文/ranking_reasons | PASS | R2 | ISSUE-LT-004(已修) | runs/round-2.md |
| answer_brain | MCP tools/call | 小白 | 真实回答/无证据 | PASS | R2 | — | runs/round-2.md（模型激活） |
| get_brain_context | MCP tools/call | 老手 | 正常/预算 | PASS | R2 | — | runs/round-2.md |
| get_self_context | MCP tools/call | 小白 | 正常/空画像 | PASS | R2 | — | runs/round-2.md |
| propose_self_claim | MCP tools/call | 小白 | 正常/非法枚举 | PASS | R2 | — | runs/round-2.md（枚举修复） |
| create_project | MCP tools/call | 老手 | 正常 | PASS | R3 | — | runs/round-3.md |
| start_task | MCP tools/call | 老手 | 正常/缺参 | PASS | R3 | — | runs/round-3.md |
| checkpoint_task | MCP tools/call | 老手 | 正常/非法task_id | PASS | R3 | — | runs/round-3.md |
| finalize_task | MCP tools/call | 老手 | 正常 | PASS | R3 | — | runs/round-3.md |
| get_project_context | MCP tools/call | 小白 | 正常/无项目 | PASS | R3 | — | runs/round-3.md |
| get_active_task | MCP tools/call | 老手 | 正常/无任务 | PASS | R3 | — | runs/round-3.md |
| get_recent_changes | MCP tools/call | 老手 | 正常 | PASS | R3 | — | runs/round-3.md |
| get_module_context | MCP tools/call | 老手 | 正常/无模块 | PASS | R3 | — | runs/round-3.md（NOT_FOUND 诚实语义） |
| search_project | MCP tools/call | 老手 | 正常/无项目 | PASS | R4 | — | runs/round-4.md（SCOPE_DENIED 权限门禁） |
| check_freshness | MCP tools/call | 老手 | 已授权/无授权 | PASS | R4 | — | runs/round-4.md（SCOPE_DENIED 权限门禁） |
| record_decision | MCP tools/call | 老手 | 正常/重复语句 | PASS | R3 | — | runs/round-3.md（去重幂等） |
| record_constraint | MCP tools/call | 老手 | 正常/重复语句 | PASS | R3 | — | runs/round-3.md（去重幂等） |
| sync_workspace | MCP tools/call | 老手 | 边界拒绝（bridge 专属） | PASS | R4 | — | runs/round-4.md（非 bridge 客户端 VALIDATION_FAILED） |
| upload_asset | MCP tools/call | 小白 | 血缘正常/非法base64 | PASS | R4 | — | runs/round-4.md（source 必须为已有 raw_input，FR-085） |
| get_operation_status | MCP tools/call | 老手 | 随机id NOT_FOUND | PASS | R4 | — | runs/round-4.md |
| create_deletion_plan | MCP tools/call | 老手 | 确认门禁 | PASS | R4 | — | runs/round-4.md（ER-06 高风险确认门禁） |
| get_deletion_plan | MCP tools/call | 老手 | 无计划 | PASS | R4 | — | runs/round-4.md（NOT_FOUND 诚实语义） |
| create_review_item | MCP tools/call | 老手 | 正常/非法枚举 | PASS | R4 | — | runs/round-4.md（枚举修复回归） |
| CLI provision-client | CLI | 管理员 | 正常 | PASS | R4 | — | runs/round-4.md |
| CLI rotate/revoke | CLI | 管理员 | 正常/已撤销 | PASS | R4 | — | runs/round-4.md（O_EXCL 防覆盖设计 + revoked 生效） |
| /ready | HTTP GET | 管理员 | 全绿/组件失败 | PASS* | R0 | — | R0 基线 |
| /health | HTTP GET | 管理员 | alive | PASS* | R0 | — | R0 基线 |
| /doctor | HTTP GET | 管理员 | 组件+metrics | PASS* | R0 | — | R0 基线（本会话新增） |
| 全套 pytest | CLI | 管理员 | 450 passed | PASS* | R0 | — | R0 基线 |
| 真实第三方客户端（Cursor/ChatGPT/Trilium） | 外部 | 管理员 | T186 矩阵 | **BLOCKED** | R0 | ISSUE-LT-001 | 缺 HTTPS/OAuth+真实账号 |

> \* 带星号 = 第 0 轮基线盘点（本会话既有实测证据），正式轮循环从 R1 起逐项**重测**（含误用/边界/恢复路径）后落非星号值。

## 覆盖统计（第 4 轮结算）

```
total_features: 35
covered: 34
pass: 34
fail: 0
blocked: 1
na: 0
cases_this_round: 23
```

> 注：30 个 MCP 工具 + CLI 生命周期均已 R4 补盲重测转正（PASS）；/ready /health /doctor /全套 pytest 维持 R0 基线证据（PASS*）。唯一 BLOCKED = ISSUE-LT-001（真实第三方客户端矩阵，外部门禁）。
