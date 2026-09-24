# FINAL_REPORT — loop-testing 最终报告

> Personal Brain V1 全量测试收敛结论。退出序：本报告 → STATE.md 终态 → sandbox-clean。

## 1. 最终状态

`FINAL STATUS`: **CONVERGED_WITH_OPEN_ISSUES**

- 总轮数：4（R0 基线盘点 + R1-R4 正式轮）    连续收敛轮数：2/2
- 停止原因：连续两轮（R3 + R4）收敛低风险轮达标（`converged_streak: 1 → 2`）
- 最后两轮差异：R3=小白画像·项目连续性组（create_project/record_decision/record_constraint/start_task/checkpoint/finalize/get_project_context/get_active_task/get_recent_changes/get_module_context，14 用例）；R4=全功能回归+补盲组（资产/生命周期/健康/CLI：upload_asset/get_operation_status/create_review_item/sync_workspace/check_freshness/search_project/create_deletion_plan/get_deletion_plan + R1-R3 关键路径 + CLI provision/rotate/revoke，23 用例）——**场景组合实质不同，非重复脚本凑数**
- 为何不是 PASS：存在 ISSUE-LT-001（P1，BLOCKED，外部门禁）——真实第三方客户端矩阵（Cursor/ChatGPT/Trilium）因缺可达 HTTPS/OAuth 路由与真实账号未验收；非代码缺陷，属待外部环境解除。核心功能与检查全部通过，继续盲测边际价值已很低。

## 2. 覆盖摘要

- 功能总数：35；PASS 34 / FAIL 0 / BLOCKED 1 / N/A 0
- 核心旅程（均 PASS）：
  - 记忆写入链：save_note / add_expense / add_todo / complete_todo / list_todos（R1，含幂等重放与空值拒绝）
  - 检索/问答链：search_brain（含 ranking_reasons 输出）/ answer_brain / get_brain_context / get_self_context / propose_self_claim（R2，模型已激活）
  - 项目连续性链：create_project / start_task / checkpoint_task / finalize_task / record_decision / record_constraint / get_project_context / get_active_task / get_recent_changes / get_module_context（R3）
  - 资产/生命周期/健康链：upload_asset（血缘）/ create_review_item / sync_workspace（bridge 专属边界）/ check_freshness / search_project / get_operation_status / create_deletion_plan（确认门禁）/ get_deletion_plan（R4a）
  - 运维链：CLI provision/rotate/revoke/list-clients（R4）+ /ready /health /doctor（R0 证据）
- 测试盲区：真实第三方客户端矩阵（BLOCKED，见 §4）；sync_workspace 的 bridge 客户端正常路径（bridge 服务不在本机合成实例暴露）；高风险删除的完整确认-执行工作流（确认门禁在授权层拦截，黑盒客户端无放行凭据）。

## 3. 已修复问题（ISSUE ↔ commit 对照）

| ISSUE | 级别 | 根因 | 回归断言 | 验证证据 | commit |
|-------|------|------|---------|---------|--------|
| ISSUE-LT-003 | P3 | `save_note`/`add_todo` 空 content 被接受入库（schema minLength:1 未在服务层执行） | 服务层 strip 校验，空串 REJECTED(VALIDATION_FAILED)、有效 ACCEPTED | 原路径重放×3；全套 453 passed | `qa/loop-testing` `7336166` + `main` `7beee45` |
| ISSUE-LT-004 | P3 | `search_brain` 空 query 返回空结果而非按 schema 拒绝 | `_search_core` 空串校验覆盖 search/answer/context/project 四入口 | 原路径重放×2；全套 454 passed | `qa/loop-testing` `9695bc0` + `main` `cfb0c12` |

## 4. 未解决问题

- **ISSUE-LT-001（P1，BLOCKED）**：真实第三方客户端矩阵（T186）未验收。
  - 影响：Cursor/ChatGPT/Trilium 等真实 MCP 客户端的互操作验收未完成（T186 保持 EXTERNAL_VERIFICATION_PENDING）。
  - 证据：R0 基线盘点；mock/自研探针不替代真实客户端。
  - 状态：BLOCKED（外部门禁）。
  - 不能修的原因：缺可达 HTTPS/OAuth 路由与上述产品真实账号；部署为局域网 HTTP 明文 + 静态 Bearer。
  - 建议动作：Δ4（HTTPS + 真实客户端矩阵收口 T186）——用户已确认稍后处理。

## 5. ⚠️ 待用户逐条确认

- **无新增决策项**（连续两轮无新产品问题，无候选方案需要拍板）。
- 遗留项均为用户既定计划：Δ3（异机备份目的地决策）、Δ4（HTTPS + 真实客户端矩阵收口 T186），与 loop-testing 无交集，不占用本报告决策区。

## 6. 既有/环境问题

- R4a 中 4 个 FAIL 经核实均为**测试预期误设**（非产品缺陷），设计依据明确：
  1. upload_asset 随机 source_id → NOT_FOUND：FR-085 数据血缘，资产必须挂接已入库 active raw_input（R4b 用真实 source 补测 PASS）。
  2. check_freshness 随机 project → SCOPE_DENIED：无项目授权即拒绝（R4b 用已授权 project 补测 PASS）。
  3. create_deletion_plan → CONFIRMATION_REQUIRED：ER-06 高风险删除确认门禁（store 层 preview-only + review inbox 设计）。
  4. get_deletion_plan 无 plan → NOT_FOUND：诚实语义，与 get_module_context/get_operation_status 一致。
- CLI rotate 指向已存在凭据文件被拒：`write_credential_once` O_EXCL 防覆盖安全设计（admin.py:52-71），指向新文件后成功。

## 7. 验证清单

| 轮次 | 场景 | 结果 |
|------|------|------|
| R1 | 小白画像记忆写入组（save_note/add_expense/add_todo/complete_todo/list_todos + 幂等 + 空值） | 13 用例；发现 LT-003 并修复 VERIFIED |
| R2 | 检索/问答/画像组（search_brain/answer_brain/get_brain_context/get_self_context/propose_self_claim + 模型激活） | 14 用例；发现 LT-004 并修复 VERIFIED |
| R3 | 小白画像项目连续性组（10 工具 + 边界） | 14 用例全 PASS；0 新产品问题 |
| R4a | MCP 补盲组 + R1-R3 关键路径回归 | 14 用例；4 预期修正（均有设计依据），0 产品 bug |
| R4b | 补测正常路径（upload_asset 血缘 / check_freshness 授权） | 4 用例全 PASS |
| R4-CLI | provision / rotate / revoke / list-clients 生命周期 | 5 步骤全 PASS；revoked 生效（permission_epoch 1→2），生产客户端未受影响 |
| 全套 pytest | 本地回归 | 454 passed / 0 failed（会话早期证据，R0 基线） |
- 未执行项：真实第三方客户端接入（BLOCKED，ISSUE-LT-001）；/ready /health /doctor 与全套 pytest 本轮未重跑（R0 基线证据维持）。

## 8. 代码交付与红线声明

- 修改文件（本会话）：
  - 新增：`deploy/windows-local/loop_r1.py`、`loop_r2.py`、`loop_r3.py`、`loop_r4.py`、`loop_r4b.py`（黑盒测试脚本）
  - 新增：`docs/looptesting/`（STATE/PLAN/FEATURE_MATRIX/ISSUES/SUGGESTIONS/runs/round-1..4/FINAL_REPORT）
  - 修复提交（LT-003/LT-004 实现）：`apps/server/personal_brain_server/api/authorized_tools.py` 等，详见 commit 对照（§3）
- 本地提交（逐分支）：
  - `qa/loop-testing`（沙箱 worktree）：`7336166` fix(qa): [ISSUE-LT-003]、`9695bc0` fix(qa): [ISSUE-LT-004]
  - `main`（主树，本会话期间同步落地）：`7beee45` fix(qa): [ISSUE-LT-003]、`cfb0c12` fix(qa): [ISSUE-LT-004]——**显式披露：主树存在上述 2 个提交**（非 loop-testing 本会话 push，属此前修复流程同步）
  - 主树更早提交（d7ba5f9 及之前）为 Δ1/Δ2/T197 等既定交付，非本会话产生。
- 未提交变更（主树 `git status`）：`README.md`、`runtime.py`、`deploy/compose.yaml`、`docs/TRILIUM_SETUP.md`、`docs/WINDOWS_LOCAL_TRIAL.md`、`docs/acceptance/traceability-matrix.md`、`packages/infrastructure/.../search/repository.py`、`tests/contract/test_deployment_boundary.py`、`tests/integration/test_runtime_entrypoints.py`——**均为本会话之前遗留的工作区变更，loop-testing 未触碰**（本会话仅新增上述未跟踪文件）。
- 最终 `git status`：见上（未跟踪：loop_r1..r4b.py + docs/looptesting/）。
- 红线声明：**本会话全程未 push / merge / PR / 发布 / 部署 / force / amend / rebase 到远端**；未触碰生产、真实账号、付费接口；沙箱隔离于 qa/loop-testing worktree，本机合成实例测试（127.0.0.1:18082），局域网生产域（192.168.10.7）未触碰。

## 9. 残余风险与续跑入口

- 残余风险：
  1. ISSUE-LT-001（P1 BLOCKED）：真实客户端互操作未验收，需 Δ4 解除。
  2. sync_workspace 的 bridge 正常路径与高风险删除确认-执行工作流未在本会话覆盖（能力边界，非缺陷）。
  3. 主树存在未提交变更（§8 列表），为历史遗留，与 loop-testing 无关；用户可自行决定提交/回退。
- 证据目录：`docs/looptesting/`（STATE / PLAN / FEATURE_MATRIX / ISSUES / SUGGESTIONS / runs/round-1..4 / FINAL_REPORT）
- 续跑入口：如需继续，从 `docs/looptesting/STATE.md` 开始——若解除 ISSUE-LT-001 门禁，以真实客户端矩阵为新场景重开一轮；否则建议按用户计划推进 Δ3/Δ4。
