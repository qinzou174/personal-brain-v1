# run round-1 — 小白画像 · 日常记录组

**round**: 1 | **日期**: 2026-09-24 | **画像**: 小白（不看文档瞎摸索） | **场景组**: save_note / add_expense / add_todo / complete_todo / list_todos / get_expense_summary

## 执行方式

通过本机 MCP 端点（127.0.0.1:18082）真实调用 `tools/call`，模拟小白用户：正常操作 + 手滑/输错/反悔/幂等重试。脚本 `deploy/windows-local/loop_r1.py`（已用后删除？否——保留为工具；证据 JSON 在 `C:\Users\槐至\AppData\Local\Temp\loop_r1.json`）。

## 用例与结果

| # | 用例 | 预期 | 实际 | 判定 |
|---|------|------|------|------|
| 1 | save_note 正常中文笔记 | accepted | accepted canonical_committed | PASS |
| 2 | save_note 同 key 幂等重放 | 同一 record_id | 同一 record_id | PASS |
| 3 | save_note 空 content | 拒绝 | **accepted** | **FAIL → ISSUE-LT-003** |
| 4 | save_note 缺 idempotency_key | 拒绝 | VALIDATION_FAILED | PASS |
| 5 | add_expense 38 CNY | accepted | accepted | PASS |
| 6 | add_expense 负数 | 拒绝 | VALIDATION_FAILED | PASS |
| 7 | add_expense 缺 currency | 拒绝 | VALIDATION_FAILED | PASS |
| 8 | add_todo 正常 | accepted | accepted | PASS |
| 9 | add_todo 空 content | 拒绝 | **accepted** | **FAIL → ISSUE-LT-003** |
| 10 | list_todos 一致性 | 含刚加的待办 | 含 | PASS |
| 11 | get_expense_summary 精确聚合 | CNY 合计含 38 | totals 126.50（含既有） | PASS |
| 12 | complete_todo 正常 | accepted | accepted | PASS |
| 13 | complete_todo 版本冲突 | VERSION_CONFLICT | VERSION_CONFLICT | PASS |

## 发现

- **ISSUE-LT-003**（P3）：save_note/add_todo 空 content 被接受入库 —— schema 有 minLength:1 但服务层未执行空串校验。

## 修复与复验

- 修复：authorized_tools.py `save_note`/`add_todo` 开头加 `if not content or not content.strip(): raise BrainError("VALIDATION_FAILED")`
- 回归测试：`tests/contract/test_empty_content_rejection.py`（3 项，worktree 3 passed）
- 提交：qa 分支 `fix(qa): [ISSUE-LT-003]`；复验同步主树 → 重启本机 → 原路径重放
- 复验结果：空串×3 全部 REJECTED、有效笔记 ACCEPTED → **VERIFIED**
- 全量回归：**453 passed / 23 skipped / 0 failed**

## 覆盖更新

- save_note / add_todo：PASS* → **PASS**（含误用/边界/幂等）
- add_expense / list_todos / get_expense_summary / complete_todo：PASS* → **PASS**

## 环境事故

- 无（本机实例已运行，未重启中途）

## 轮末结算

- cases_this_round: 13
- 发现：P3×1（ISSUE-LT-003）
- 修复并 VERIFIED：1
- 遗留：0（本轮）
- 收敛判定：**非收敛轮**（发现 P3 新问题）→ converged_streak 保持 0
- 下轮重点：老手画像 · 记忆/检索组（search_brain / answer_brain / get_brain_context / get_self_context / propose_self_claim）