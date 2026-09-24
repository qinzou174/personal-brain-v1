# 历史阶段与接续文档（2026-09-24）

> **本文件用途**：新对话窗口接续工作的唯一入口。先读本文件，再按需读它引用的证据文档。
> **权威性**：任务状态以 `specs/001-personal-brain-v1/tasks.md` 为准；本文件是快照与索引，不替代它。
> **取代关系**：本文件取代 `docs/acceptance/implementation-handoff.md`（后者停留在 2026-09-23，任务数与测试数均已过期）。

---

## 一、项目一句话定位

Personal Brain V1 是**单用户、证据驱动的可信记忆与上下文基础设施**：独立于任何模型/账号/客户端，任何客户端可换，记忆不换，且每条结论都能追溯到原始证据。

- 规格：`specs/001-personal-brain-v1/`（spec / plan / tasks / contracts / data-model / execution-rules）
- 四条不可让渡公理（来自设计反思文档）：权威单一且服务端、原始先于派生、权限先于检索、诚实优先于成功
- ER 规则（`execution-rules.md`）是硬约束，其中 ER-06（确认门）、ER-07（幂等/断网四态）、ER-12（模型预算 fail-closed）在改造时最容易被踩

---

## 二、当前状态快照（2026-09-24）

| 项 | 状态 |
|---|---|
| 任务 | **195/197 已勾选**，未勾 2 项：T186、T197 |
| 本机全量测试 | **431 passed / 23 skipped / 0 failed**（本轮实测） |
| 隔离 PostgreSQL 全量 | 本轮未重跑；上一轮为 440 passed / 12 skipped |
| 迁移 head | **0012_search_read_grants**（链 0001..0012） |
| 版本控制 | ⚠️ **git 仓库无任何提交**，全部文件处于 untracked 状态（见"坑"第 1 条） |
| 本机实例 | `127.0.0.1:18082`，`/ready` 全绿，已重启至最新代码 |
| 局域网实例 | `192.168.10.7:18081`，镜像 `personal-brain-v1-runtime:local` → `92627dd3869d`，`/ready` 全绿 |
| 真实个人数据 | **未导入**（仍处门禁后） |

### 未勾选的 2 项

- **T186**（EXTERNAL_VERIFICATION_PENDING）：真实客户端矩阵 Trilium / TRAE CN / Cursor / ChatGPT 的端到端验收。**卡点：需要可达的 HTTPS + OAuth 路由**，纯局域网明文 HTTP 走不通标准客户端。mock 不能替代。
- **T197**（EXTERNAL_VERIFICATION_PENDING）：为本机实例提供 Ark key 密钥文件，重启后验证真实接地 `answer_brain` 与向量检索。**卡点：本机 `E:\Personal-Brain-V1-local\secrets\model-api-key` 不存在**，故本机 `external_models_enabled=false`（局域网实例已有该 key，模型可用）。

---

## 三、历史阶段

| 阶段 | 内容 | 证据 |
|---|---|---|
| Phase 0 | 只读调查 | `docs/environment-report.md`、`docs/deployment-decision.md` |
| Phase 2 | Foundation：幂等、审计、日志、作业存储、协议信封、OAuth PKCE、provider 网关、preflight、Dockerfile/compose | `foundation.md` |
| Phase 3–14 | US1..US12 逐用户故事落地（生活记录、溯源、自我模型、项目连续性、上下文检索、资产、安全/桥、生命周期删除、离线、运维恢复、主动性、人机界面）；迁移 0002..0011 | `us1-*` .. `us12-*` |
| Phase 15 | 发布：13 份文档、ER-12 容量/中文检索、9 条合成旅程、客户端矩阵、追溯矩阵、最终就绪评审 | `er12-benchmark-2026-09-23.md`、`client-matrix.md`、`final-readiness-review.md` |
| Phase 16 | 收敛：受控持久化删除、OAuth bearer 身份映射、隔离 PG 迁移链 | `governed-deletion-2026-09-23.md`、`oauth-provider-hardening-2026-09-23.md`、`migration-postgresql-2026-09-23.md` |
| Phase 17 | 生产闭环（T188–T192）：容器/发布边界、Compose secrets、迁移门禁启动、owner/client CLI、精确项目授权、部署旅程、重启持久化 | `production-runtime-2026-09-23.md` |
| Phase 18 | Windows 本机实例（T193–T196）：便携 PG16+pgvector、过期租约回收与中文短语检索修复、本机 API/worker、启停脚本与重启持久化 | `windows-local-trial-2026-09-24.md` |
| **Phase 19（本会话）** | **F1 授权缺陷修复、MCP 协议互操作修复、可观测性补齐、局域网部署与实测、凭据轮换** | 见第四节 |

---

## 四、本会话（2026-09-24）做了什么

### 4.1 F1 缺陷修复：`search_brain` 授权与契约不一致

**问题**：`search_brain` 对所有 scope 硬编码 `tool="knowledge.read"`，导致只持有领域授权（`todo.read`/`finance.read`…）的客户端在非 knowledge 作用域模糊检索时被 `SCOPE_DENIED`，且与权威契约（`tool-contracts.md` 规定 `search.read`）分歧。

**改动**：
- `apps/server/personal_brain_server/api/authorized_tools.py`
  - 抽出 `_search_core(...)`：只做路由与检索，不做二次授权
  - `search_brain` → `search.read`；`get_brain_context` → `context.read`；`search_project` → `project.read` + `project:<id>`
  - `answer_brain` 保持 `knowledge.read`，改为 3 次 recheck（源读取前 / 模型调用前 / 响应前）
  - 新增私有 `_expense_summary` / `_todo_records`，使精确路由由契约指定工具治理
- `apps/server/personal_brain_server/admin.py`：`DEFAULT_TOOLS` 增加 `search.read`/`context.read`；`_TOOL_SCOPE` → `_TOOL_SCOPES`，开通时按 (工具 × 作用域) 逐条授权
- `migrations/versions/0012_search_read_grants.py`（新）：为既有活跃客户端回填授权，**不扩大**其作用域集合，不建表，downgrade 只删本版插入行
- `specs/001-personal-brain-v1/contracts/tool-contracts.md`、`docs/MCP_TOOLS.md`：补充逐作用域授权说明
- `tests/security/test_search_read_authorization.py`（新，11 测）
- 证据：`docs/acceptance/search-read-authorization-fix-2026-09-24.md`

### 4.2 MCP 协议互操作修复（两处与规范不一致）

**问题**：
- (A) `initialize` 也强制要求 `MCP-Protocol-Version` 头 —— 规范只要求 initialize **之后**的请求携带
- (B) `params.protocolVersion` 不等于 `2025-11-25` 直接 400 —— 规范要求服务端**回协商版本**

两者都会在握手阶段挡掉标准客户端（含手机端 App）。**均不影响认证/授权**。

**改动**：
- `apps/server/personal_brain_server/protocols/remote.py`：版本头改为 initialize 可选；initialize 之后仍必需且必须匹配
- `apps/server/personal_brain_server/protocols/mcp_dispatcher.py`：`initialize` 改为协商，缺 `protocolVersion` 仍拒
- `tests/contract/test_mcp_dispatcher.py`（+2 测）
- 证据：`docs/acceptance/mcp-protocol-negotiation-fix-2026-09-24.md`

**未改**：`GET /mcp` 仍返回 405（规范允许不支持 SSE 的服务端这样响应）。

### 4.3 可观测性补齐

原构建 `access_log=False` 且 `logging` 模块（`bootstrap/logging.py` 的 `RedactingFilter`/`CorrelationFormatter`）未接入，日志只有启动信息，无法排查。

- `protocols/remote.py`：新增 `_logger`，BrainError 与 parse error 分支输出**无正文** warning（只记 status/code/HTTP 方法，不含 body、凭据、客户端身份 —— 符合 FR-070/FR-073）
- `__main__.py`：`access_log=True`

### 4.4 局域网部署与实测

- 同步改动文件到 `/home/kms/personal-brain-v1`（哈希校验一致）→ `docker compose build api && up -d` → migrate 自动跑 0011→0012
- 部署前保护：`pg_dump` 备份至 `/home/kms/personal-brain-v1-backups/predeploy/`；旧镜像打标签 `personal-brain-v1-runtime:pre-f1-rollback`
- 实测通过：`/ready` 全绿；不带版本头+旧版本号握手 → 200（协商到 2025-11-25）；后续不带版本头 → 400；带正确头 → 200（30 工具）
- 完整 E2E（脚本内从文件读 token，不经过对话）：initialize 200 → notifications/initialized 202 → tools/list 30 → list_todos → save_note（返回 operation_id/persistence/record_id/source_id/status）→ **同 idempotency_key 重放结果完全一致**
- 日志验证：容器日志同时出现 access 行与 `mcp rejected status=400 code=VALIDATION_FAILED method=POST`

### 4.5 凭据轮换（安全事件处置）

`Mobile Terminal` 客户端（`client_id 338eb047-6af7-4f8d-a0a1-ec6b8370c90c`）的 bearer token 曾被明文粘贴进对话，**视为已泄露**：

- 已执行 `rotate-client`，旧 token 实测返回 **401**（失效）
- 新凭据只写入服务器文件 `/home/kms/personal-brain-v1-data/secrets/mobile-credential`（`-rw-------`），**未进入任何对话文本**
- 容器内临时副本已删除

### 4.6 TRAE CN 两个 MCP 条目核查

`%APPDATA%\Trae CN\User\mcp.json` 共 3 条目，其中两个是 personal-brain 变体：

| 条目 | 后端 | 凭据文件 | 实测 |
|---|---|---|---|
| `personal-brain` | `192.168.10.7:18081`（局域网） | `C:\Users\槐至\.personal-brain\trae-cn-credential` | initialize 通过、30 工具、`search_brain` 返回 hits |
| `personal-brain-local` | `127.0.0.1:18082`（本机） | `E:\Personal-Brain-V1-local\secrets\windows-trial-credential` | initialize 通过、30 工具、`list_todos` 返回正常 |
| `justoneapi` | 云端 | — | — |

**两者连的是两个独立数据库**，用户已决定**都保留**（用于本机/局域网对照测试）。二者在 TRAE CN 列表里同名显示，因为桥会透传服务端 `serverInfo.name = "personal-brain"`。

---

## 五、下一步（按优先级）

1. **T197（本机真实模型）**：把 Ark key 放到 `E:\Personal-Brain-V1-local\secrets\model-api-key`，重启本机实例（`start.ps1` 会自动检测并置 `external_models_enabled=true`），验证真实接地 `answer_brain` 与向量检索。
2. **手机端接入**：三条路已明确（见第六节"手机接入现状"）。若用户要 App 方案，需先解决 HTTPS；若走 Termux 脚本则当前即可用。
3. **T186（真实客户端矩阵）**：需可达的 HTTPS + OAuth 路由，才能跑 Trilium / Cursor / ChatGPT。这是唯一"改架构才能过"的门禁。
4. **版本控制**：仓库无任何提交，建议尽快建立基线提交（需用户确认，见"坑"第 1 条）。
5. **设计决策待拍板**：`docs/tasks/design-20260924-能力对比与智能路线/02-思考路径.md` 提出 D1–D5（动作结果算不算事实 / 主动性上限 / 是否引入外部代发面 / ER-12 预算域怎么分 / 循环宿主放哪），**尚未决策，未动代码**。

---

## 六、操作手册

### 本机实例（Windows）

```powershell
# 启动（uv 不在 PATH，必须先补）
$env:PATH = "C:\Users\槐至\.local\bin;" + $env:PATH
& "e:\新建文件夹\Personal-Brain-V1\deploy\windows-local\start.ps1"
# 停止
& "e:\新建文件夹\Personal-Brain-V1\deploy\windows-local\stop.ps1"
```

- 运行时根目录：`E:\Personal-Brain-V1-local`（PG 数据 `pgdata`、密钥 `secrets`、日志 `*.log`、PID `*.pid`）
- PostgreSQL：`127.0.0.1:55432`；API：`127.0.0.1:18082`

### 局域网实例（192.168.10.7）

```bash
ssh codex-kms                      # HostName 192.168.10.7, User kms
cd /home/kms/personal-brain-v1/deploy
docker compose build api && docker compose up -d   # migrate 服务自动 alembic upgrade head
docker compose ps
```

- 代码目录 `/home/kms/personal-brain-v1`；数据/密钥 `/home/kms/personal-brain-v1-data`；备份 `/home/kms/personal-brain-v1-backups`
- 服务：`api`(18081) / `worker` / `db`(pgvector:pg16) / `model-proxy`(host 网络 + unix socket) / `migrate`
- 外部模型：Ark（`deepseek-v4.1-flash` + `doubao-embedding-vision`，1024 维）

### 管理 CLI

```bash
docker compose exec -T api python -m personal_brain_server list-clients --json
docker compose exec -T api python -m personal_brain_server rotate-client --client-id <id> --credential-file <path>
docker compose exec -T api python -m personal_brain_server revoke-client --client-id <id> --confirm-client-id <id>
docker compose exec -T api python -m personal_brain_server provision-client --name <n> --client-type <t> --credential-file <path>
```

### 当前 MCP 客户端

| 客户端 | client_id | 作用域 |
|---|---|---|
| Mobile Terminal（mobile） | `338eb047-6af7-4f8d-a0a1-ec6b8370c90c` | knowledge/finance/todo/self/asset/review/operations/projects |
| TRAE CN（stdio-bridge） | `18166334-725a-43ee-89d8-ee341dfd01a6` | 上述 + `project:22676290-8cb5-4411-8252-8d3b7eafe4bb` |

**未开放**：`diary` 作用域（请求返回 `SCOPE_DENIED`，属正确行为）。

### 日志监听

局域网容器日志后台监听输出至 `C:\Users\槐至\AppData\Local\Temp\pb_lan_logs.txt`。

### 手机接入现状

| 路径 | 可行性 |
|---|---|
| Termux（Android）跑脚本 | ✅ 当前即可用，绕开 HTTPS/OAuth 限制 |
| Joey MCP Client（iOS/Android，开源） | ⚠️ 待实测，需支持明文 HTTP + 静态 bearer |
| 加 HTTPS 隧道（Cloudflare Tunnel / Tailscale） | ✅ 正解，同时解锁 T186 |

阻塞手机 App 的四点：明文 `http://`（iOS ATS / Android 9+ 默认禁）、私有 IP 需本地网络权限、静态 bearer 而非 OAuth、必须带 `MCP-Protocol-Version: 2025-11-25` 且 `GET` 返 405。

---

## 七、坑与注意事项

1. **仓库无任何 git 提交**：`git log` 报 "does not have any commits yet"，所有文件 untracked。任何"回滚"都没有基线可用。建议先建基线提交（需用户确认）。
2. **`uv` 不在 PATH**：`C:\Users\槐至\.local\bin\uv.exe`。运行 `start.ps1` 前必须前置 PATH，否则 `Get-Command uv` 直接抛错。
3. **`stop.ps1` 会一并停 PostgreSQL**：若之后要跑 `alembic upgrade head`，会连接超时。需先单独 `pg_ctl start`，迁移后再 `start.ps1`。
4. **陈旧 `postmaster.pid`**：本机 PG 启动可能报 "another server might be running"；确认 PID 进程不存在后删除该文件即可（环境残留，非产品缺陷）。
5. **杀 uv 后 python 子进程可能残留**：会占住 18082，导致 `start.ps1` 报 "Port 18082 is already in use by an unmanaged process"。用 `Get-NetTCPConnection -LocalPort 18082` 找到 PID 再 `Stop-Process`。
6. **桥接对 `notifications/initialized` 会输出一行 `{}`**：严格按 JSON-RPC 规范 notification 不应有响应行。TRAE CN 可容忍，**未改动**。
7. **测试并行会污染全局计数**：可靠性测试与桥接测试并行时，`life_tools` 的全局 store 行计数会被并发写入干扰，出现假失败。需单独重跑或用 `reset_store()`。
8. **环境门禁项不勾选、不伪造**：PG DSN、真实客户端、Ark key 等保持 `EXTERNAL_VERIFICATION_PENDING`，mock 不能替代真实客户端。
9. **部署前务必先备份**：`pg_dump` + 旧镜像打标签，是唯一可用的回滚手段（因无 git 基线）。

---

## 八、设计反思文档（另一条工作流，未动代码）

`docs/tasks/design-20260924-能力对比与智能路线/`（本仓库 `docs/tasks/` 首建）：

- `01-对比报告.md`：AnythingLLM / Personal Brain V1 / OpenClaw·Hermes 三者能力矩阵
- `02-思考路径.md`：结论为"项目不是不够聪明，是没有手和闹钟"；30 个工具全是记录/查询/计划动词，无动作型；`answer_brain` 硬限 1 次模型调用是架构天花板；全仓零通道代码；**ER-03 规定的 `ranking_reasons` 代码零实现（规范写了没接线）**

**待用户拍板的 5 个决策点（D1–D5）尚未决策**，因此**未做任何代码改动**。

---

### 4.7 修复 `complete_todo` 500：`todos` 表缺失 `updated_at` 列（代码/迁移漂移）

**现象**：Zafiro 客户端 `complete_todo` 返回 `500`，空响应体，日志报
`sqlalchemy.exc.CompileError: Unconsumed column names: updated_at`。

**根因**：迁移链 [0002_life_records.py](file:///e:/%E6%96%B0%E5%BB%BA%E6%96%87%E4%BB%B6%E5%A4%B9/Personal-Brain-V1/migrations/versions/0002_life_records.py#L116-L136) 创建 `todos` 表时**刻意不含 `updated_at`**（手写 `created_at/completed_at/archived_at/version`，未用 `_timestamps()`），而 [authoritative_store.py](file:///e:/%E6%96%B0%E5%BB%BA%E6%96%87%E4%BB%B6%E5%A4%B9/Personal-Brain-V1/packages/infrastructure/personal_brain_infra/persistence/authoritative_store.py#L771-L774) 的 `complete_todo` 却写入 `updated_at=now`。二者不一致 → `metadata.reflect()` 出的表无该列 → UPDATE 编译失败。

**为何本机测试全绿**：测试用 `tests/integration/test_authoritative_store.py` 里手工 `_schema()`（其 `common()` 含 `updated_at`）+ `metadata.create_all()` 建库，**与迁移链建出的 schema 不一致**，掩盖了该缺陷。服务器是迁移链建的真实库，因此暴露。

**修复**：`complete_todo` 的 `.values()` 去掉 `updated_at=now`，与迁移设计对齐（`todos` 有意用 `completed_at` 表达完成时刻）。

**验证**：
- 本地回归：`tests/integration tests/contract tests/security` → **145 passed**
- 服务器重建镜像（`personal-brain-v1-runtime:local`）后，Zafiro `complete_todo` 返回 `200`，待办落库 `state=completed version=2`
- 容器日志近 5 分钟 **0 条 500 / 0 条 Unconsumed column**

**后续注意**：`todos` 是唯一刻意不含 `updated_at` 的表；其余表经 `_timestamps()` 都有该列。后续若有人给 `todos` 补 `updated_at`，需同步迁移。

---

## 九、接续起点建议

新窗口第一件事：

1. 读本文件 + `specs/001-personal-brain-v1/tasks.md` 的未勾选项
2. 跑一次本机全量回归，确认是否仍为 **431 passed / 23 skipped / 0 failed**；有偏差必须先解释再下结论
3. 问用户本轮目标：T197（本机模型）/ 手机接入 / T186（HTTPS+OAuth）/ 设计决策 D1–D5 / 建 git 基线
