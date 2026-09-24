# ISSUES — 问题总账（第 0 轮建立）

> 发现即立案，逐条追加，禁止静默修复。P0-P3 分级。
> 状态机：`OPEN → REPRODUCING → FIXING → FIXED_UNVERIFIED → VERIFIED → CLOSED`；可回 `OPEN`。

| ID | 级别 | 标题 | 状态 | 复现/证据 | 修复提交 | 复验 | 备注 |
|----|------|------|------|----------|----------|------|------|
| ISSUE-LT-001 | P1 | 真实第三方客户端矩阵（T186）未验收 | BLOCKED | 缺可达 HTTPS/OAuth 路由与 Cursor/ChatGPT/Trilium 真实账号；mock 不替代 | — | — | 外部门禁，非代码缺陷；解除条件=提供真实环境 |
| ISSUE-LT-002 | P3 | 本机实例曾残留 4 个 dead_letter 作业 | CLOSED | 2026-09-24 `/doctor` 首次暴露 failed_jobs=4（refresh_project_context） | 已在会话清理（DELETE） | 已验证 0 | 冒烟测试残留；doctor 可见性价值实证 |
| ISSUE-LT-003 | P3 | `save_note`/`add_todo` 空 content 被接受入库（schema minLength:1 未执行） | VERIFIED | R1 实测 `{"content":""}` 返回 accepted+canonical_committed（2 个实例） | qa 分支 + 主树 `fix(qa): [ISSUE-LT-003]` | 原路径重放：空串×3 REJECTED、有效 ACCEPTED；453 passed | 同根因（服务层空串校验缺失）；违反 FR-009 低价值不入库精神 |
| ISSUE-LT-004 | P3 | `search_brain` 空 query 未按 schema 拒绝（返回空结果而非 VALIDATION_FAILED） | VERIFIED | R2 实测 `{"query":""}` 返回 `{"authority":"hybrid","hits":[],"semantic_status":"unavailable"}` | qa 分支 + 主树 `fix(qa): [ISSUE-LT-004]` | 原路径重放：空 query×2 REJECTED、有效 ACCEPTED；454 passed | 与 LT-003 同根因扩展：检索入口空串校验缺失 |

## 待确认 / 待拍板（NEEDS_CONFIRMATION）

- 无（第 0 轮）
