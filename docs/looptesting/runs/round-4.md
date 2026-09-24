# run round-4 — 全功能回归 + 补盲组（资产/生命周期/健康/CLI）

**round**: 4 | **日期**: 2026-09-24 | **画像**: 老手/管理员 | **场景组**: upload_asset / get_operation_status / create_review_item / sync_workspace / check_freshness / search_project / create_deletion_plan / get_deletion_plan + R1-R3 关键路径回归 + CLI 生命周期

## 执行方式

- **R4a**：本机 MCP 端点 `tools/call` 黑盒，脚本 `deploy/windows-local/loop_r4.py`，证据 JSON：`C:\Users\槐至\AppData\Local\Temp\loop_r4.json`
- **R4b**：补测正常路径（血缘/授权前置条件），脚本 `deploy/windows-local/loop_r4b.py`，证据 JSON：`C:\Users\槐至\AppData\Local\Temp\loop_r4b.json`
- **CLI 生命周期**：`personal_brain_server provision/rotate/revoke/list-clients` 真实命令（`BRAIN_ENVIRONMENT=test` 指向本机合成库）

## 用例与结果

### R4a MCP 补盲组 + 回归（14 项）

| # | 用例 | 预期 | 实际 | 判定 |
|---|------|------|------|------|
| 1 | upload_asset 随机 source_id | accepted | NOT_FOUND | **PASS*** |
| 2 | upload_asset 非法 base64 | 拒绝 | VALIDATION_FAILED | PASS |
| 3 | get_operation_status 随机 id | 拒绝 | NOT_FOUND | PASS |
| 4 | create_review_item 正常 | accepted | canonical_committed + review_item_id | PASS |
| 5 | create_review_item 非法枚举 | 拒绝 | VALIDATION_FAILED | PASS |
| 6 | sync_workspace 非 bridge 客户端 | 拒绝 | VALIDATION_FAILED | PASS |
| 7 | check_freshness 随机 project | fresh 报告 | SCOPE_DENIED | **PASS*** |
| 8 | search_project 无项目权限 | 拒绝 | SCOPE_DENIED | PASS |
| 9 | create_deletion_plan 无确认 | accepted | CONFIRMATION_REQUIRED | **PASS*** |
| 10 | get_deletion_plan 无 plan | plan 报告 | NOT_FOUND | **PASS*** |
| 11 | save_note 回归 | accepted | canonical_committed | PASS |
| 12 | add_expense 回归 | accepted | canonical_committed | PASS |
| 13 | search_brain 回归（含 ranking_reasons） | hits+reasons | hybrid + `ranking_reasons:["freshness=fresh","source=canonical"]` | PASS |
| 14 | get_self_context 回归 | claims | 10 条 claims | PASS |

### R4b 补测正常路径（4 项，4 PASS）

| # | 用例 | 预期 | 实际 | 判定 |
|---|------|------|------|------|
| 1 | save_note 前置（血缘 source） | accepted | canonical_committed | PASS |
| 2 | upload_asset 真实 source_id | accepted | asset_id + blob_id 返回 | PASS |
| 3 | check_freshness 已授权项目 | fresh 报告 | `{"fresh":true,"modules":[]}` | PASS |
| 4 | check_freshness 无授权项目 | 拒绝 | SCOPE_DENIED | PASS |

### R4 CLI 生命周期（5 项，5 PASS）

| # | 用例 | 预期 | 实际 | 判定 |
|---|------|------|------|------|
| 1 | list-clients --json | 客户端清单 | 2 个客户端（LT-Test-Client + Windows-Local-Trial） | PASS |
| 2 | provision-client | active + credential 文件 | `client_id + status:"active"` | PASS |
| 3 | rotate-client（新凭据文件） | rotated + 旧凭据 revoke | `status:"rotated"` | PASS |
| 4 | revoke-client（confirm 一致） | revoked | `status:"revoked"` | PASS |
| 5 | 复查 list-clients | revoked 生效 | LT-Test-Client `status:"revoked"` permission_epoch 1→2；Windows-Local-Trial 未受影响 | PASS |

> 注：rotate 首次尝试指向**已存在**凭据文件被拒（`write_credential_once` O_EXCL 防覆盖，admin.py:52-71 安全设计），改为指向新文件后成功。**测试预期修正，非产品缺陷**。

## 测试预期修正（非产品缺陷，均已核实设计依据）

| 用例 | 初始预期 | 实际 | 设计依据 |
|------|----------|------|----------|
| upload_asset 随机 source | accepted | NOT_FOUND | FR-085 数据血缘：资产必须挂接已入库 active raw_input（`authoritative_store.py` upload_asset 校验 source 存在） |
| check_freshness 随机 project | fresh 报告 | SCOPE_DENIED | 无项目授权即拒绝，与 search_project 一致 |
| create_deletion_plan 无确认 | accepted | CONFIRMATION_REQUIRED | ER-06 高风险删除确认门禁（`authorized_tools.py` risk="high_risk_deletion"）；store 层为 preview-only + review inbox 设计 |
| get_deletion_plan 无 plan | plan 报告 | NOT_FOUND | 诚实语义：plan 不存在报告 NOT_FOUND（与 get_module_context/get_operation_status 一致） |

## 发现

- **无新产品问题**。（4 项测试预期误设，均已对照设计与契约核实）

## 修复与复验

- 无代码改动。前两轮修复（LT-003/LT-004）回归路径全 PASS，无回退。

## 覆盖更新

- upload_asset / get_operation_status / check_freshness / search_project / sync_workspace / create_deletion_plan / get_deletion_plan / create_review_item / CLI provision / CLI rotate-revoke：PASS* → **PASS**（全部补盲重测）
- /ready /health /doctor /全套 pytest：本轮未重跑，维持 R0 证据

## 环境事故

- 无（临时凭据文件 `lt-tmp-credential`、`lt-tmp-credential-rotated` 已清理，revoke 闭环）

## 轮末结算

- cases_this_round: 14（R4a）+ 4（R4b）+ 5（CLI）= **23**
- 发现：0 新产品问题（4 测试预期修正，全部有设计依据）
- 修复并 VERIFIED：0
- 遗留：0（ISSUE-LT-001 外部门禁除外）
- 收敛判定：R3（0 bug）+ R4（0 bug）连续两轮收敛低风险轮 → `converged_streak: 1 → 2` → **CONVERGED**
- 退出：满足收敛条件，进入 exit-and-report（sandbox 清理 + FINAL_REPORT）
