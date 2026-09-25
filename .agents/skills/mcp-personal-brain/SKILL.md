---
name: mcp-personal-brain
description: 对接 Personal Brain 生产实例（HTTPS + natfrp 隧道）。用于把个人知识/项目/画像写入长期知识库、检索问答、管理项目任务。当用户要"记到个人知识库""问我以前记过什么""把这个项目写进知识库"或任何需要访问 Personal Brain 的 MCP 工具时使用。凭据从环境变量或密钥文件读取，不在本 skill 硬编码。
---

# MCP-Personal-Brain（个人知识库对接）

Personal Brain V1 生产实例对接说明。核心链路：**任何 MCP 客户端（Trae/Cursor/自研）→ HTTPS 隧道 → nginx → Personal Brain API → PostgreSQL(pgvector)**。

## 0. 端点与凭据（重要：不硬编码）

### 生产端点（服务器 A 同级目录部署）
```
Base:   https://www.h2d954063.nyat.app:43086/brain/mcp
协议:   MCP 2025-11-25 Streamable HTTP
认证:   Authorization: Bearer <credential>
版本头: MCP-Protocol-Version: 2025-11-25
会话:   initialize 后必须回传 MCP-Session-Id（后续请求都带）
```

### 凭据获取（三选一，禁止写死）
1. **环境变量** `BRAIN_MCP_CREDENTIAL`——设置后直接使用；
2. **密钥文件** `E:\Personal-Brain-V1-local\secrets\prod-trial-credential`（本机本地实例）或服务器 `personal-brain-v1-prod-data/secrets/`；
3. 向用户索要（provision 的新客户端凭据）。

> 安全红线：凭据属于敏感信息，不得写入任何被 git 追踪的文件、日志或 prompt 输出。若环境变量缺失，先检查密钥文件，仍无则询问用户，**不要编造或硬编码**。

## 1. 会话建立（每次新对话/新会话必须先 initialize）

```python
# 摘自我的探针脚本：deploy/windows-local/mcp_tunnel_smoke.py
call("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                    "clientInfo": {"name": "my-client", "version": "1"}})
# 响应头 MCP-Session-Id 必须存下来，后续请求带上
call("notifications/initialized", {}, None)  # 通知完成初始化
call("tools/list", {})  # 应返回 37 个工具（2026-09-25 起，含 update_note/delete_todo/correct_expense）
```

## 2. 工具速查（37 个，按使用场景分组）

### 日常记录（高频）
- `save_note(content, requested_scope="knowledge", idempotency_key)` — 记笔记/日记/知识，原样入库并自动向量化
- `update_note(old_note_id, content, requested_scope="knowledge", idempotency_key)` — **更正笔记**：写入更正版（新 record_id），旧笔记退出检索视野（响应 `superseded_id` 指向旧条目）；旧条目不存在/已更正 → NOT_FOUND
- `add_expense(amount, currency, category, description, occurred_timezone, requested_scope="finance", idempotency_key)` — 记账（金额走精确 SQL，不要用语义搜索代替）
- `correct_expense(expense_id, new_amount, requested_scope="finance", idempotency_key)` — **更正账目**：旧账归档+新账生效（描述加「更正」前缀），汇总立即正确（响应 `corrected_from`）；非法金额 in-band VALIDATION_FAILED
- `add_todo(content, requested_scope="todo", idempotency_key[, priority])` / `complete_todo(todo_id, expected_version, ...)` / `delete_todo(todo_id, expected_version, ...)`（直接删除，重复删 NOT_FOUND）/ `list_todos`
- `list_expense_records` / `get_expense_summary([currency])`

### 检索问答（高频）
- `search_brain(query, requested_scope, sensitivity_ceiling="private", limit[, time_from, time_to])` — 混合检索（FTS+向量+排序），返回带 `ranking_reasons`；命中摘录已自动聚焦到匹配位置（前 5 条）；可选 `time_from`/`time_to`（ISO 日期，"2026-09-01" 即整天）按内容时间过滤，无时间戳卡片在给定时诚实排除
- `get_entry_content(entry_id, sensitivity_ceiling="private")` — **fetch-after-search**：按 search_brain 返回的 `entry_id` 取该条目全文。消费检索结果的标配两步：先 search 定位、再 fetch 全文。不存在/超敏感度/源已删一律诚实 `NOT_FOUND`；授权自动落在条目自身 scope（复用 search.read），无需额外授权
- `answer_brain(query, requested_scope, ...)` — **仅凭库内证据回答**，grounded=True；无证据时明确答"无法确认"
- `get_brain_context(intent, requested_scope, detail, budget)` — 拿到上下文包（intent 需是真实检索意图词，传 "general" 会空）

### 自我画像
- `get_self_context(categories, requested_scope="self")` — 查看画像 claims
- `propose_self_claim(category, claim_text, policy_class=A/B/C, requested_scope="self", idempotency_key)` — A=立即生效，B=候选，C=待用户确认（重大价值观）；与既有主张同主题极性相反时响应带 `conflict_warning`（提示不阻止）

### 项目工作流
- `create_project`（同名存活项目时响应带 `duplicate_name_hint`；创建者自动获 project.read/write/review.write@project:\<id\>，可直接发起删除计划）/ `record_decision` / `record_constraint` / `start_task` / `checkpoint_task` / `finalize_task` / `get_project_context` / `get_active_task` / `get_module_context` / `get_recent_changes` / `check_freshness` / `search_project`

### 治理/资产（低频）
- `upload_asset`（source_id 必须指向已有 active raw_input，否则 NOT_FOUND——血缘设计）
- `create_deletion_plan`（高风险确认门禁，返回 CONFIRMATION_REQUIRED 是正常语义）
- `create_review_item` / `resolve_review_item`（对已裁决项重复操作返回 ALREADY_RESOLVED——幂等语义不是错误）/ `list_review_items` / `get_deletion_plan` / `list_projects` / `get_operation_status`（正常路径用真实 operation_id）/ `sync_workspace`（仅 bridge 客户端）

## 3. 边界与错误码（对接必备）

| 错误 | 含义 | 处理 |
|------|------|------|
| AUTH_INVALID | 凭据/session 无效 | 重新 provision/确认凭据，重开会话 |
| SCOPE_DENIED | 该 scope 无授权 | 用正确的 requested_scope（账目=finance，项目=projects，知识=knowledge） |
| VALIDATION_FAILED | 参数不合 schema | 检查必填空值；**不要传 schema 之外的字段**（additionalProperties:false） |
| NOT_FOUND | 目标不存在 | 查询不存在的 id 时是诚实语义，如 get_module_context 对未注册模块 |
| CONFIRMATION_REQUIRED | 高风险操作需确认 | 理解这是门禁，不是失败 |
| ALREADY_RESOLVED | 审核项已完成裁决 | 幂等状态：轮询后重试会拿到它，直接视为已处理 |
| TOOL_DENIED | 模型网关未配置 | 环境缺 Ark key |

关键约定（踩坑总结）：
- **记账/待办是结构化数据**：问"花了多少钱"走 finance SQL 精确路径；不要在 knowledge scope 里搜账目（账目只索引在 finance scope）。
- **idempotency_key 必须每次传新 uuid**：幂等闸门，重发同一 key 返回原结果不重复入库。
- **checkpoint_task/finalize_task 的可选参数**（revision/end_revision/end_dirty_state）不传是合法的——契约已对齐。
- **删除/审查类要过确认门禁**：这是 ER-06 设计，不是 bug。待办删除/笔记更正/账目更正属低风险直改（003-correction-delete-ux），无需门禁。
- **写后检索有数秒延迟**：写响应带 `index_state: "pending"`，检索卡由后台作业异步建立。

## 4. 快速探测（验证链路，参考脚本）

```bash
# Windows 本机探针（需 uv/python）
uv run python deploy/windows-local/mcp_tunnel_smoke.py   # 30 工具
uv run python deploy/windows-local/mcp_tunnel_exec.py    # 实测写入一条
```

## 5. 服务器侧部署路径（只读参考，勿随意改）

- 代码：`/home/kms/personal-brain-v1-prod`（与 A、nas 同级）
- compose：`deploy/compose.prod.yaml`（project=personal-brain-v1-prod，端口 18083）
- 密钥：`/home/kms/personal-brain-v1-prod-data/secrets/`（db_dsn / db_password / token_pepper / model_api_key）
- nginx：`/etc/nginx/conf.d/wangzhan1.conf` 的 `location /brain/mcp` → `192.168.10.7:18083/mcp`
- 隧道：natfrp wangzhan1 隧道 → `www.h2d954063.nyat.app:43086` → 本机 nginx