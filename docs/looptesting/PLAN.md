# PLAN — 测试计划（第 0 轮产出）

> 第 0 轮生成，后续轮次可追加，不覆盖历史。
> 本 PLAN 由 loop-testing skill 在 2026-09-24 生成，针对 Personal Brain V1 项目做全量测试。

## 1. 产品形态与真实入口

- 产品形态：**API/服务 + CLI + 后台任务（worker）+ 库（domain/infra 包）组合**
  - 主入口：MCP 协议端点（Streamable HTTP + stdio bridge），暴露 30 个工具
  - 辅助入口：管理 CLI（`python -m personal_brain_server provision-client/rotate-client/...`）、健康端点（`/ready` `/health` `/doctor`）、后台 worker 作业
- 真实入口（用户可达）：
  - MCP 端点（本机实例）：`http://127.0.0.1:18082/mcp`（MCP 2025-11-25，Bearer 认证）
  - 管理 CLI：`uv run python -m personal_brain_server <subcommand>`
  - 健康/就绪：`GET /ready` `GET /health` `GET /doctor`
  - 30 个 MCP 工具：get_brain_context / search_brain / answer_brain / get_self_context / get_expense_summary / list_expense_records / list_todos / get_project_context / get_module_context / search_project / get_active_task / get_recent_changes / check_freshness / save_note / add_expense / add_todo / complete_todo / start_task / checkpoint_task / finalize_task / record_decision / record_constraint / sync_workspace / upload_asset / get_operation_status / create_project / propose_self_claim / create_review_item / create_deletion_plan / get_deletion_plan
- 发现依据：README.md、docs/MCP_TOOLS.md、specs/001 与 002 的 tool-contracts、`apps/server/personal_brain_server/protocols/tools.py`（FR099_TOOL_NAMES 30 项）、既有 pytest 套件（450 passed）

## 2. 启动与基线命令

- 安装：`uv sync`（已有 venv）
- 启动本机实例：`deploy/windows-local/start.ps1`（PostgreSQL 16 + pgvector + API 18082 + worker，模型已激活）
- 测试：`uv run pytest -q` → 基线 450 passed / 23 skipped / 0 failed
- lint：无独立 lint 配置（项目依赖 pytest + 类型注释）
- 健康：`GET /ready` → 全绿；`GET /doctor` → overall healthy

## 3. 角色与典型旅程

- 角色（按 skill 双重身份）：
  - **小白**：第一次接触、不看文档瞎摸索的普通用户（通过 MCP 客户端）
  - **老手**：每天重度使用的效率用户（用脚本批量调工具）
  - **管理员**（本机 operator）：管理 CLI、健康检查、备份
- 关键业务旅程：
  1. 日常记录：一句话同时产生 Expense + Todo（US1）
  2. 记忆助手：存笔记 → 搜索 → 追问 answer_brain（US2/US3）
  3. 项目连续性：create_project → start_task → checkpoint → finalize（US4）
  4. 恢复：断聊后 get_project_context / get_active_task 恢复（US4/SC-004）
  5. 运维：/doctor 查看失败 job、备份脚本 dry-run（US10）

## 4. 场景设计（每功能至少：正常 / 边界 / 误用 / 取消·恢复）

| 功能 | 正常路径 | 边界值 | 错误输入·误用 | 取消/刷新/恢复 | 注意细节 |
|------|---------|--------|--------------|---------------|---------|
| save_note | 存一条中文笔记，返回 canonical_committed | 超长文本（1MiB 上限内）、emoji/多语言 | 空 content、缺 idempotency_key、非法 scope | 同 key 重放幂等 | 触发索引 job |
| add_expense | 记账 38 CNY | 负数/零、多币种、退款 | 非法 amount 格式、currency 缺失 | 同 key 重放 | 精确聚合 |
| add_todo | 加待办 | 超长 content、priority 越界 | 空 content | 完成/取消流转 | — |
| complete_todo | 完成待办 | 不存在的 todo_id | 非法 UUID、版本冲突 | 重复 complete | updated_at 缺陷已修 |
| list_todos | 列出待办 | 空列表 | 无权限 scope | — | 归档语义 |
| search_brain | 全文+向量混合检索 | 中文短语、超长 query（8k 上限） | 空 query、越权 scope | — | ranking_reasons 可解释 |
| answer_brain | 真实模型接地回答 | 无证据问题 | 无模型权限 TOOL_DENIED | — | grounded 诚实 |
| get_brain_context | intent 路由上下文 | summary/normal/deep 预算 | 非法 intent | — | 预算兜底 |
| get_self_context | 自画像查询 | 空画像 | 越权 | — | A/B/C 状态 |
| propose_self_claim | 提交 A/B/C 画像 | 非法 category 枚举 | 无 idempotency_key | — | 枚举 500 已修 |
| create_project | 建项目 | 超长 name | 空 purpose | — | 授权门禁 |
| start_task / checkpoint / finalize | 任务生命周期 | 缺参 | 非法 task_id | 断点续跑 | revision/dirty 证据 |
| record_decision / constraint | 记录决策约束 | 重复语句 | 无项目权限 | — | 去重幂等已修 |
| sync_workspace | 工作区同步 | 无 Git 仓库 | 越界路径 | 边界拒绝 | bridge 专属 |
| upload_asset | 上传文件 | 大文件（≤100MiB）、重复哈希 | 非法 base64 | 幂等 | 内容寻址 |
| create_deletion_plan / get_deletion_plan | 删除预览 | 不存在的目标 | 越权 | 确认门禁 | ER-09 |
| create_review_item | 入 Inbox | 非法 item_type 枚举 | — | — | 枚举 500 已修 |
| get_operation_status | 查询操作 | 随机 id NOT_FOUND | — | — | 诚实语义 |
| CLI provision/rotate/revoke/list | 客户端生命周期 | 已撤销再调用 | 凭据冲突 | — | 密钥轮换实测 |
| /ready /health /doctor | 健康检查 | 组件失败不塌 HTTP | — | — | doctor 详情已暴露 |

## 5. 测试盲区（能力所限，如实登记）

- **无真实第三方客户端**（Cursor/ChatGPT/Trilium 真实账号 + HTTPS/OAuth）→ T186 真实客户端矩阵为 BLOCKED（外部门禁），本轮以本机 MCP 端点 + stdio bridge 行为验证替代，不冒充真实客户端验收。
- **无 Web/UI**：本项目无前端，UI 面 N/A。
- **局域网生产域（192.168.10.7）不触碰**：红线——只测本机合成实例（127.0.0.1:18082），绝不触碰真实数据/生产系统。
- 沙箱 worktree（qa/loop-testing）用于代码修复的原子提交；本机实例复验需把修复同步到主树后重启（主树干净、无用户未提交内容，安全）。
- MoA 多模型：本地单模型环境，`scripts/moa.mjs` 需要 Node + 多模型 key；不可用则降级单模型记录在 `decisions/DEC-*`。

## 6. 沙箱与环境就绪

- 沙箱方式：**worktree** `E:/新建文件夹/Personal-Brain-V1-qa-loop`（qa/loop-testing 分支，baseline=qa-baseline）
- 种子数据 / 测试凭证：本机实例使用 windows-trial 凭据（`E:\Personal-Brain-V1-local\secrets\windows-trial-credential`）+ 合成笔记/支出/待办；CLI 用本机 PG（127.0.0.1:55432）
- 基线检查结果：`/ready` 全绿、`/doctor` overall healthy、`uv run pytest -q` = **450 passed / 23 skipped / 0 failed**（2026-09-24，本会话实测）
- 沙箱隔离自证闸：exit 0、ownership.env 存在、worktree list 含 qa-loop、主树仍在 main、`.active` 哨兵在 —— **已全部核验通过**