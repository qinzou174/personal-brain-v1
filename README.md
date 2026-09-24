# Personal Brain V1

私有、证据可溯、单所有者的个人知识库：一个权威存储、原文先行采集、结构化精确记录、
项目连续性、有界检索、治理化生命周期。

> **一句话**：把"AI 对你的了解"和"你和 AI 一起干活的进度"从聊天窗口里搬进一个
> 自有服务器上的仓库——聊天窗口随便换、随便丢，账永远在。

## 为什么做这个

正常对话里 AI 靠上下文记忆：时间越久上下文越大，记忆延续越好；但换个对话框
（哲学、理念、计划、任务、项目进度全没了）或换个软件（AI 对你的理解也没了）。

本项目用**仓库模型**替代"链子模型"：

| | 上下文记忆 | 知识库记忆 |
|---|---|---|
| 本质 | 越聊越长的对话链 | 原文档案 + 索引卡 + 画像 |
| 找回方式 | 往回翻整条链 | 按需检索，最相关的几条塞回上下文 |
| 换窗口/换软件 | 全部清零 | 连上同一个库，记忆全在 |
| 时间越久 | 越长越贵 | 越值钱（索引越全、画像越准） |

## 核心能力

### 六个内容域（写入即索引，写入即可检索）

| 域 | 工具举例 | 用途 |
|---|---|---|
| knowledge | `save_note` / `answer_brain` | 笔记、踩坑记录、收藏（全文+语义双路检索） |
| finance | `add_expense` / `get_expense_summary` | 记账与汇总 |
| todo | `add_todo` / `complete_todo` | 待办清单（版本号防并发冲突） |
| self | `propose_self_claim` / `get_self_context` | AI 对你的理解（画像，见下） |
| asset | `upload_asset` | 文件资产（上传文本自动入索引） |
| projects | `create_project` / `start_task` / `checkpoint_task` / `finalize_task` 等 | 项目连续性（见下） |

### 项目工作流（换对话框不丢进度）

```
create_project 立项 → start_task 开工（goal/revision/脏状态）
  → record_decision 定方案 / record_constraint 画红线
  → checkpoint_task 阶段存档 → finalize_task 收工（生成变更事件）
任何新会话：get_project_context / get_active_task / get_recent_changes / check_freshness
```

- 新会话一次调用即可找回"当前任务 + 干完什么 + 下一步"
- 版本栅栏：项目在别处被改动后，旧上下文会收到漂移警告
- 历史任务**永久保留**（退出"当前"视图但可检索），删除必须走治理审批

### 画像系统（AI 对你的理解）

- **A 类**：亲口立的规矩，立即生效，永不自动过期
- **B 类**：观察候选，≥3 来源 + 跨 14 天 + ≥2 场景才转正
- **C 类**：随记，90 天无新证据自动淡出
- 重复（相似度 ≥88%）自动进审批盒合并；矛盾不自动裁决，等你拍板

### 治理与审批

删除计划、画像合并、矛盾复核全部走 `review_inbox_items` → 通知盒
（`notifications`）→ `resolve_review_item`（带确认单：限时 15 分钟、单次有效、
绑定身份）→ 执行/作废。**系统永不自动删项目事实**。

### 有界检索

双路检索（jieba 关键词 + pgvector 语义）→ RRF 融合排序（可解释：
`ranking_reasons` 带 freshness/canonical 依据）→ 按客户端授权作用域裁剪。
越权作用域在访问索引前即被拒绝。

## 架构

```
MCP 客户端（Trae / Cursor / 手机端 / 自研）
   │  Streamable HTTP (JSON-only)，MCP 2025-11-25
   ▼
apps/server  ── 协议层（dispatcher/remote）→ 授权（authority + policy）
   │                                  → 幂等（client_id+op+key 去重/冲突检测）
   ▼
packages/infrastructure ── 权威存储（authoritative_store，PostgreSQL+pgvector）
   │                     ── 检索（RRF 融合）── 作业（durable jobs 表）
   ▼
apps/worker ── 后台作业：extract / index_* / refresh_project_context
              / notify_review / 摘要 / 画像演化 / 冲突扫描 / 清理
```

- **技术栈**：Python 3.12、SQLAlchemy 2、Alembic（迁移链 0001..0013）、
  PostgreSQL 16 + pgvector、jieba FTS、MCP 2025-11-25、Docker Compose
- **安全模型**：OAuth bearer + permission_epoch、作用域授权矩阵
  （`review.write@<内容域>` 等细粒度）、敏感内容隔离（疑似凭据只建关键词卡、
  跳过语义处理）、审计留痕

## 目录结构

```
packages/domain/personal_brain_domain      领域不变量（策略/规则/契约）
packages/infrastructure/personal_brain_infra  持久化/存储/检索/作业/安全
apps/server/personal_brain_server          API 与 MCP 协议适配
apps/worker/personal_brain_worker          后台作业处理器
apps/bridge/personal_brain_bridge          工作区边界的本地桥
migrations/versions                        Alembic 迁移链 0001..0013
deploy/                                    部署编排与脚本（compose.prod.yaml 等）
deploy/windows-local/                      本机运维工具链（凭据零硬编码，见下）
tests/{unit,contract,integration,security,migration,acceptance,restore}
specs/001-personal-brain-v1                规格/计划/任务/契约
docs/                                      运维与客户端文档（见索引）
```

## 快速开始（本地开发）

```powershell
# 1. 依赖与数据库（本地 PostgreSQL 16 + pgvector，或 compose 起 db）
uv sync
$env:BRAIN_TEST_POSTGRES_DSN='postgresql+psycopg://brain:<pw>@127.0.0.1:55432/brain_test'

# 2. 全量测试（真实 PG harness；部分用例无 DSN 时自动跳过）
uv run pytest tests -q --ignore=tests/benchmark

# 3. 启动（stdio 桥本机试用）
uv run python -m personal_brain_bridge
```

测试基线：**584 passed / 12 skipped / 0 failed**（2026-09-25，迁移链 0013）。
测试哲学：先写失败测试 → 实现 → 回归 → 证据存档 `docs/acceptance/`。

## 生产部署（Linux）

- 编排：`deploy/compose.prod.yaml`（db/worker/model-proxy 内网，api 绑定
  `192.168.10.7:18083`）；迁移由独立 `migrate` 服务在启动前自动执行
- 服务器目录（2026-09-25 重组）：

```
/home/kms/deploy/personal-brain/
├── prod/          代码（部署 = git pull + compose up -d --build）
├── prod-data/     secrets 与运行时挂载（db_password/db_dsn/token_pepper/model_api_key）
├── backups/       每日加密备份包（.tar.age + sha256）
└── backup-input/  backup-keys/   备份中转与密钥
```

- 部署命令见 `deploy/compose.prod.yaml` 头注释；**secrets 目录必须与 db 容器
  挂载一致**，否则迁移步密码认证失败
- 备份：服务器 `deploy/scripts/prod-backup.sh`（加密打包）→ 本机
  `uv run python deploy/windows-local/pull_backup.py`（异机副本 + sha256 校验）
- 健康检查：`GET /doctor`（disk/jobs/assets/relations 四组件 + findings）

## MCP 客户端接入

33 个工具，接入细节见 [`docs/zafiro-client-onboarding.md`](docs/zafiro-client-onboarding.md)
（握手三步、幂等键规则、错误码表、凭据轮换）。要点：

- `initialize` → 回传 `MCP-Session-Id` → 之后每请求带 `MCP-Protocol-Version: 2025-11-25`
- 所有写操作带 `idempotency_key`（重试复用同一 key；同 key 不同参数 → `IDEMPOTENCY_CONFLICT`）
- 工具内业务错误：HTTP 200 + `result.isError=true + structuredContent.code`
- 局域网端点 `http://192.168.10.7:18083/mcp`；外网走 HTTPS 隧道

## 本机运维工具链（deploy/windows-local/）

**凭据零硬编码**：所有 SSH 工具经 [`_ssh.py`](deploy/windows-local/_ssh.py) 读
`BRAIN_SSH_PASSWORD` 环境变量或 [`_local_creds.txt`](deploy/windows-local/_local_creds.txt)
（gitignored，一行密码）。新机器 clone 后建这个文件即可使用：

| 工具 | 用途 |
|---|---|
| `server_exec.py <cmd>` | 服务器执行单条命令 |
| `run_remote_sh.py <script.sh>` | 本地脚本管道到远端 bash -s（规避引号转义） |
| `server_sql.py "<sql>"` | 生产库只读 SQL |
| `tail_prod_logs.py <秒>` | api/worker 日志增量落盘到 docs/acceptance/ |
| `pull_backup.py` | 拉取最新备份包到本机并校验 |
| `fetch_logs.py <cmd>` | 带异常输出的命令执行 |

## 文档索引

| 文档 | 内容 |
|---|---|
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | 用户工作流与概念 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构与模块边界 |
| [docs/DATA_MODEL.md](docs/DATA_MODEL.md) | 数据模型与迁移 |
| [docs/MCP_TOOLS.md](docs/MCP_TOOLS.md) | 33 工具契约 |
| [docs/SECURITY.md](docs/SECURITY.md) | 授权/幂等/敏感内容 |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | 部署与服务器布局 |
| [docs/BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md) | 备份/恢复（已实证） |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | 运维手册 |
| [docs/PERSONAL_BRAIN_RULES.md](docs/PERSONAL_BRAIN_RULES.md) | 执行规则（ER-01..ER-12） |
| [docs/zafiro-client-onboarding.md](docs/zafiro-client-onboarding.md) | MCP 客户端接入 |
| [docs/acceptance/](docs/acceptance/) | 全部验收证据（含两轮 chain-audit） |

## 状态

- 迁移链 0001..0013；全量回归 **584 passed / 12 skipped / 0 failed**
- 2026-09-25 两轮 chain-audit：静态 8 绳 34 项（5×P1+10×P2 已修）+ 生产活体系审
  （5 内容域写入→索引→检索→治理删除全链实测，零死信）；详见
  [docs/acceptance/chain-audit-live-2026-09-25.md](docs/acceptance/chain-audit-live-2026-09-25.md)
- 已知未修（低优先级）：未知工具错误码与 MCP 规范 `-32602` 的偏差（P3）、
  Bridge 离线队列接线、digest 跨日补算
