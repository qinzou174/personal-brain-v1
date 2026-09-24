# run round-2 — 老手画像 · 记忆/检索组

**round**: 2 | **日期**: 2026-09-24 | **画像**: 老手（高效、批量、要可解释） | **场景组**: search_brain / answer_brain / get_brain_context / get_self_context / propose_self_claim

## 执行方式

本机 MCP 端点真实调用 `tools/call`。证据 JSON：`C:\Users\槐至\AppData\Local\Temp\loop_r2.json`。

## 用例与结果（14 项，12 过 2 待判）

| # | 用例 | 预期 | 实际 | 判定 |
|---|------|------|------|------|
| 1 | search_brain 正常（西湖） | 命中+ranking_reasons | 3 hits 全部带 ranking_reasons | PASS |
| 2 | search_brain 空 query | 拒绝 | 空结果非报错 | FAIL → ISSUE-LT-004 |
| 3 | search_brain 越权 scope(diary) | SCOPE_DENIED | SCOPE_DENIED | PASS |
| 4 | answer_brain 正常 | grounded 真实回答 | 答"杭州"、grounded=True、诚实声明时间先后不确定 | PASS |
| 5 | get_brain_context summary/deep | 预算内 | PASS（×2） | PASS |
| 6 | get_brain_context invalid detail | 默认兜底 | 正常返回 | PASS |
| 7 | get_self_context | 画像含 A/B/C claim | 含 value/interest 等 | PASS |
| 8 | propose_self_claim A/B/C | accepted | 3 项 accepted canonical_committed | PASS |
| 9 | propose_self_claim 非法 category | VALIDATION_FAILED | VALIDATION_FAILED | PASS |

> 注：脚本统计的 answer_brain.grounded 一条为**测试脚本判断 bug**（`ok` 被赋为字符串），已核对产品行为 grounded=True 正常，非产品问题。

## 发现

- **ISSUE-LT-004**（P3）：search_brain 空 query 未按 schema 拒绝（返回空结果）—— 与 LT-003 同根因扩展，检索入口空串校验缺失。

## 修复与复验

- 修复：`_search_core` 入口加空 query 校验（`if not query or not query.strip(): raise BrainError("VALIDATION_FAILED")`）—— 覆盖 search_brain / answer_brain / get_brain_context / search_project 四个共用入口
- 回归测试：`tests/contract/test_empty_content_rejection.py` 增 1 项（worktree 4 passed）
- 提交：qa 分支 `fix(qa): [ISSUE-LT-004]`；复验同步主树 → 重启本机 → 原路径重放
- 复验结果：空 query×2 REJECTED、有效 ACCEPTED → **VERIFIED**
- 全量回归：**454 passed / 23 skipped / 0 failed**

## 覆盖更新

- search_brain / answer_brain / get_brain_context / get_self_context / propose_self_claim：PASS* → **PASS**

## 环境事故

- 无

## 轮末结算

- cases_this_round: 14
- 发现：P3×1（ISSUE-LT-004）
- 修复并 VERIFIED：1
- 遗留：0（本轮）
- 收敛判定：**非收敛轮**（发现 P3 新问题）→ converged_streak 保持 0
- 下轮重点：小白画像 · 项目连续性组（create_project / start_task / checkpoint_task / finalize_task / get_project_context / get_active_task / get_recent_changes / record_decision / record_constraint）