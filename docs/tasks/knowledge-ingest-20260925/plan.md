# 计划表：知识库存入工程

> 配套总览见 [README.md](./README.md)。本文档是唯一执行依据：每批按条目顺序写入，每批结束跑该批验收查询，通过才进下一批。

---

## 批次 0：前置检查

| # | 检查项 | 方法 | 通过标准 |
|---|---|---|---|
| 0.1 | 执行通道可用 | 方案 A：Trae CN 的 `mcp_personal-brain_*` 工具；方案 B（默认兜底）：探针脚本直连隧道（`BRAIN_MCP_CREDENTIAL` 读 `E:\Personal-Brain-V1-local\secrets\prod-trial-credential`） | `initialize` 200 + `tools/list` 33 个 |
| 0.2 | 生产健康 | `mcp_tunnel_smoke.py` | 33 tools，无 AUTH_INVALID |
| 0.3 | 查重 | `search_project("Personal Brain V1")` + `search_brain("系统工程 立项", scope=projects)` | 无同名存活项目才 create；已有则改为补齐模块地图 |
| 0.4 | 凭据红线自查 | 本计划全部条目扫一遍 | 无任何凭据/密码/key 内容 |

> 2026-09-25 已验证：通道 B 连通（33 工具在线）。通道 A 当前在 Trae CN 会话内报 "MCP tool is not found"（bridge 工具注册丢失），需在 Trae 重启 MCP 服务器后恢复；不阻塞执行。

---

## 批次 1：骨架批（立项 + 七模块地图）

**1.1 `create_project`**

- name：`Personal Brain V1 个人知识库系统`
- purpose：`Python + PostgreSQL/pgvector 的个人长期记忆系统；MCP 2025-11-25 协议对外，六内容域（notes/todo/finance/knowledge/projects/self）+ 治理闭环。本工程沉淀其架构决策、硬约束、运维经验与任务线。`

**1.2 `sync_workspace`（modules 参数，逐模块写入，共 7 条）**

| 模块 | 地图要点 |
|---|---|
| domain | 纯领域层：实体模型、BrainError 错误码、执行规则（ER-01..ER-07）定义；零外部依赖，被所有层引用 |
| infrastructure | pgvector 仓储、迁移执行器、资产存储、ModelGateway（预算/超时/sensitivity/凭据拒收）、密钥文件读取 |
| server | MCP 分发器（mcp_dispatcher）、33 工具面、FastAPI 运行时（/doctor /ready 门禁）、OAuth 认证链 |
| worker | 作业调度器（daily_digest 03:10 / promote 04:10 / retention 04:20+04:40 / conflict_scan 04:30 / health 08:00）、索引作业、LLM 日配额 200 |
| bridge | stdio MCP 代理：本地客户端 → RemoteMCPProxy → 远端 /mcp；stdout 只走协议行 |
| deploy | compose（5 服务 + 日志轮转）、prod 布局 /home/kms/deploy/personal-brain/{prod,prod-data,backups,backup-input,backup-keys}、备份/恢复脚本、windows-local 运维脚本族 |
| docs-tests | docs/acceptance 验收体系、er12 基准、584 集成测试、e2e_postgres_harness |

**批次 1 验收**

- `get_project_context` 返回 7 模块
- `get_module_context("server")` 能取到 server 地图
- `search_project("模型网关 fail-closed")` 命中 infrastructure 或 server 模块

---

## 批次 2：规则批（decision ×10 + constraint ×10）

**2.1 `record_decision`（每条含"为什么"）**

| # | 决策 | 原因锚点 |
|---|---|---|
| D1 | RRF 融合分是唯一跨列表排序权威；长度归一化只留在词法列表内部（ts_rank_cd 密度式） | 融合分区间 0.009~0.033，长度罚项跨 10 倍会压死长档案（实证："壁纸"档案词法+语义双 rank1 仍跌出前 30） |
| D2 | OAuth 认证必须接入运行时认证链；OAuthBearerAuthority 包装器委托全部变更型方法 | 否则 MCP 路径静默失效（create_project 后 creator 无 self-grant） |
| D3 | provider/LLM 调用必须经 ModelGateway 有界执行；无 gateway 时 fail-closed | 预算/超时/敏感度/凭据拒收必须有统一闸门 |
| D4 | 迁移链 0001..0013 以 down_revision 串联；实体只创建一次，后续迁移只引用 | 可重放、可回滚（restore 兜底） |
| D5 | 金额意图路由：必须带"钱/元/块/¥"或明确金额词，否则保守走混合检索 | 禁止宽泛子串判断，防止误路由（router 28 项矩阵测试固化） |
| D6 | RAG 场景默认关闭 deepseek-v4.1 思考模式 | 避免 token 消耗超限 |
| D7 | 索引类作业（index_*）执行时重读当前行、豁免版本检查；写作业版本栅栏保留 | 索引是派生数据，重读不丢真值；写作业栅栏防并发覆盖 |
| D8 | 画像 B→established 升级四条件：≥3 来源、≥14 天、≥2 上下文、无矛盾 | 防止单次陈述污染长期画像 |
| D9 | 冲突处理：同主题相反极性记 conflicts + 生成 Inbox 待办，不自动降 confidence | 极性矛盾应交人裁决，机器单方降权会掩盖真冲突 |
| D10 | 重复已删除语句按生命周期分支回放：存活→duplicate，已删→tombstone | 幂等重放语义诚实 |

**2.2 `record_constraint`**

| # | 约束 |
|---|---|
| C1 | 凭据/密码/key 只走 env 或密钥文件，禁止硬编码入任何 git 追踪文件、日志、prompt（2026-09-25 安全审查裁决） |
| C2 | 幂等键每次新 uuid；重发同 key 返回原结果，不得当新写入 |
| C3 | 账目是结构化数据：金额查询走 finance 精确 SQL，禁止用 knowledge 语义搜索替代 |
| C4 | `docker compose exec -T` 在 bash -s 管道中必须 `</dev/null`（所有行，不只 cleanup 行） |
| C5 | `rotate-client` 前必须先 rm 容器内目标文件（遇已存在文件静默抛 FileExistsError 被 tail 吞） |
| C6 | compose file-secret 在 CLI 读不了 0600 源文件时静默跳过挂载（v5.3.1）——ops token 等敏感挂载一律走目录 bind |
| C7 | 服务器目录 mv 后必须 `up -d --force-recreate` 才能让 bind 挂载真正切换 |
| C8 | project-access / review-access bump epoch 后必须 rotate-client 刷新凭据 |
| C9 | docker 日志时间戳为 UTC（北京+8）；考古排查一律先换算 |
| C10 | 授权门禁：无实现授权不动手；真实数据导入必须在恢复验证之后 |

**批次 2 验收**

- `search_project("排序 RRF 长度")` 命中 D1
- `search_project("幂等")` 命中 C2 / D10
- `search_brain("exec -T stdin", scope=projects)` 命中 C4

---

## 批次 3：经验批（save_note，scope=knowledge，统一标签前缀）

| # | 标题 | 标签 |
|---|---|---|
| N1 | 【坑】compose file-secret 静默跳过挂载——现象/定位（compose config 渲染 vs 容器 inspect 对比）/绕行 | 坑, 部署 |
| N2 | 【坑】PowerShell 5.1 向 curl 传 JSON 剥双引号——改 `--data @file` / Out-File ascii | 坑, windows |
| N3 | 【坑】BOM 文件导致 bash 首行报错——用 .NET WriteAllText 写 sh | 坑, windows |
| N4 | 【坑】rotate-client 残留 /tmp 目标文件静默失败——epoch 链完整重跑 | 坑, 凭据 |
| N5 | 【验收】安全审查 2026-09-25：4 项发现（硬编码/文档泄露/端点暴露/脚本滞留）全修复；遗留=本机测试库密码轮换、SSH 密钥化 | 验收, 安全 |
| N6 | 【验收】活体系审 2026-09-25：5 域写入→索引→检索、幂等/协议/治理闭环全通，dead_letter=0；报告 chain-audit-live-2026-09-25.md | 验收, 链审 |
| N7 | 【交接】部署布局 v2：/home/kms/deploy/personal-brain 五件套；secrets 实路径；旧 stack 已清理归档 | 交接, 部署 |
| N8 | 【备注】Trae CN 对接配置：bridge 三 env（CLIENT_ID / REMOTE_MCP_URL:18083 / CREDENTIAL_FILE）+ 凭据文件位置 | 备注, 对接 |

**批次 3 验收**

- `search_brain("file-secret 静默跳过")` 命中 N1
- `search_brain("安全审查 遗留")` 命中 N5

---

## 批次 4：动态批

| # | 工具 | 内容 |
|---|---|---|
| T1 | `start_task`（挂本项目） | 任务"知识库存入工程收尾"：completed_work=四批写入完成情况；next_step=终验与后续维护约定 |
| T2 | `add_todo` | B1：未知工具名应返回 -32602 而非 -32000（mcp_dispatcher.py:135），待拍板是否修 |
| T3 | `add_todo` | 轮换本机测试库 PG 密码（前 8 位已随 git 历史公开） |
| T4 | `add_todo` | 服务器 SSH 密钥化（密码认证仍开） |
| T5 | `propose_self_claim`（A 类 ×3） | 工作方式：偏好 env 引用拒绝硬编码；工具/SDK 装 D 盘；解释偏好白话+实例 |
| T6 | `propose_self_claim`（B 类 ×1） | 系统控制：关键触发器偏好固定逻辑而非 LLM 决策（候选，观察升级） |

**批次 4 验收**

- `get_active_task` 返回 T1
- `list_todos` 含 3 条新待办
- `get_self_context` 出现新 claim（A 类即时，B 类在候选区）

---

## 终验（全部批次后）

1. **存量清点**：`get_project_context` 模块数=7；decision/constraint 计数=10+10；笔记 8 条；待办 3 条。
2. **检索抽查**：从上面各批验收查询中随机抽 4 组复跑，全部命中且 `ranking_reasons` 合理。
3. **幂等验证**：任取一条写入的同 idempotency_key 重放，返回原结果、计数不变。
4. **红线复核**：对库做 `search_brain("password credential 密钥", sensitivity_ceiling=normal)`，确认无凭据类内容入库。
5. **收尾**：`checkpoint_task` 记录终验结果 → 本文件夹 README 勾状态 → 结果摘要回执给用户。

---

## 执行通道约定

- **方案 A（首选）**：Trae CN `mcp_personal-brain_*` 工具。前提：MCP 服务器重启后工具注册恢复。
- **方案 B（兜底，已验证）**：临时探针脚本直连 `https://www.h2d954063.nyat.app:43086/brain/mcp`（凭据经 env 注入，脚本用完即删，不落聊天）。写入与验收查询全部可走此通道。
- 两条通道共用同一 prod-trial 身份，权限一致（knowledge/self/projects 域可用，finance 未授权）。
