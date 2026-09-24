# Chain-Audit 报告：Personal Brain V1 全链路审查（2026-09-25）

> 方法：chain-audit（侦探式链路追踪）——8 根绳子逐条拉通，每环问「上游/逻辑/下游消费」，
> 断点回代码与生产库双向核实。**只读审查，未改任何代码**；修复需另行授权。
> 环境：生产 `192.168.10.7:18083`（api/worker/db/model-proxy + nginx/HTTPS 隧道）+ 本机 PostgreSQL 测试库。
> 本次由主审 + 4 条并行子链路调查（摄入/授权/部署/协议）交叉完成，主观判断项均已回主代码复核。

## 0. 系统全景（本项目版）

| 系统 | 职责 | 关键文件 | 本次经过的绳子 |
|---|---|---|---|
| 协议层 MCP | 会话/版本/错误码/工具面 | `protocols/remote.py`、`mcp_dispatcher.py`、`tools.py` | E |
| 授权层 | 认证/scope/敏感度/epoch | `security/authority.py`、`domain/security/policy.py` | C、E |
| OAuth 提供方 | 授权码→令牌→grant 校验 | `security/oauth.py`、`oauth_grants.py` | C、E |
| 摄入 | 幂等→intake→raw_input→排作业 | `persistence/authoritative_store.py:63-232`、`idempotency.py` | A |
| 结构化存储 | todos/expenses/projects/tasks/facts | `authoritative_store.py` | A、C |
| 索引与检索 | jieba FTS + pgvector + RRF | `search/indexer.py`、`repository.py` | A |
| 模型网关 | LLM/embedding 有界调用 | `infra/models/gateway.py`、`volcengine.py`、`server/model_proxy.py` | A、B |
| 调度器 | 每本地日 7 类周期作业 | `worker/scheduler.py` | B |
| LLM 派生 | 抽取候选/每日摘要 | `worker/extraction.py`、`digest.py`、`llm_budget.py` | B |
| 画像演化 | 晋升/过期/冲突/去重 | `worker/evolution.py`、`claim_dedupe.py` | B、C |
| 治理 | 复核项/删除计划/审计 | `domain/operations/*`、`worker/deletion_jobs.py` | C |
| 通知 | 健康失败主动通知 | `worker/notification_jobs.py`、`domain/operations/notification_*.py` | B |
| 资产 | 上传/解析/血缘 | `infra/assets/derivation.py`、`storage/*` | A |
| 运维 | 健康/备份/日志/迁移 | `runtime.py`、`bootstrap/logging.py`、`deploy/scripts/*`、`migrations/0001..0012` | D |
| Bridge | 工作区同步（本地 CLI） | `apps/bridge/*` | E |

## 1. 绳子清单与覆盖

| 绳 | 入口 | 覆盖 |
|---|---|---|
| A 摄入→存储→索引→检索 | 12 个写类 MCP 工具 | **WALKED** |
| B 调度→LLM 派生→演化→摘要→通知→预算 | worker 调度 tick / 作业表 | **WALKED** |
| C 授权→治理→删除 | 全部 33 工具的 authorize + 删除链 | **WALKED** |
| D 部署→配置→迁移→运维 | compose/脚本/迁移/健康端点 | **WALKED** |
| E 协议→OAuth→客户端 | `/mcp` 请求 → 响应 | **WALKED** |
| F 备份→恢复 | `deploy/scripts/*` | **WALKED（发现两套机制并存）** |
| G Bridge→sync_workspace | `apps/bridge` CLI | **PARTIAL（契约比对完成，端到端未跑）** |
| H 迁移链 | 0001..0012 | **WALKED（线性、PG 扩展有镜像支撑、抽查列名一致）** |

## 2. 断点清单（P1 优先）

### P1

**P1-1 `/doctor` 的资产与关系检查从未生效（假健康）**
- 白话：健康报告里"资产损坏数 / 关系断裂数"永远是"没检查"，因为 SQL 查了两个不存在的列名，报错又被静默吞掉。
- 举例：生产 `/doctor` 返回 `"assets":"not_checked","relations":"not_checked"` 且 `corrupted_assets:-1, broken_relations:-1`——`-1` 就是"查失败"的哨兵值；即使真有损坏资产，体检也只会说 healthy。
- 证据：`apps/server/personal_brain_server/runtime.py:76-86`（查 `assets.integrity`、`relations.target_id`）vs 生产库实列 `assets.integrity_state`、`relations.subject_id/object_id`（`migrations/0006:36,85`、`0002:188,213`）；异常在 `runtime.py:85-86` 被 `except SQLAlchemyError: pass` 吞掉。
- 严重度：**P1**（观测失明：整个"资产完整性/关系完整性"体检是装饰）。
- 断点位置：运维观测链 → doctor probe。

**P1-2 `Origin` 允许列表为空且无法配置，任何带 Origin 的客户端一律 401**
- 白话：服务端留了个"只允许白名单来源"的检查，但白名单是空的、也没有任何配置入口——于是浏览器类/带 Origin 头的 MCP 客户端永远连不上，而且报的是 401（像是凭据错）。
- 举例：用浏览器或发 `Origin: https://claude.ai` 的 MCP 客户端调用 → `validate_origin` 抛 `AUTH_INVALID` → HTTP 401；客户端会以为密钥失效而去轮换凭据，越修越乱。
- 证据：`apps/server/personal_brain_server/__main__.py:270-273`（`allowed_origins=()`）→ `protocols/remote.py:22-31,58-59`；`Settings` 里没有对应字段（`bootstrap/settings.py` 全字段）。
- 严重度：**P1**（对接天花板：一类客户端零可用，且症状误导）。
- 断点位置：协议链 → 传输准入。

**P1-3 OAuth 资源标识硬编码内网 http 地址，与 HTTPS 隧道入口不匹配**
- 白话：OAuth 的"目标资源"写死成 `http://192.168.10.7:18083/mcp`，而手机/外部客户端实际走 `https://…nyat.app/brain/mcp`；OAuth 要求资源标识严格相等，于是外部 OAuth 客户端拿到的令牌内在受众对不上，无法通过校验。发现端点也回内网地址。
- 举例：外部客户端按 `/.well-known/oauth-protected-resource` 发现 `resource=http://192.168.10.7:18083/mcp`（内网地址），随后按隧道地址换来的令牌 audience 永远不等。
- 证据：`__main__.py:182-189`（`base = f"http://{public_host}:{bind_port}"`，scheme 写死 http）、`__main__.py:271`；校验在 `security/oauth.py`/`oauth_runtime.py` + `oauth_grants.py:72,107`（audience 严格相等）。
- 严重度：**P1**（T186 真实客户端 OAuth 验收的真正拦路虎；手机端目前用静态 Bearer 才绕过）。
- 断点位置：协议链 → OAuth 受众绑定。

**P1-4 备份只有本机形态、两套机制并存，且无不一致检测**
- 白话：备份脚本有的依赖 `/tmp` 固定文件与输入目录（上一会话 T183 的验证流程），有的用环境变量；两者互不兼容，且都只落在本机磁盘——用户早就担心的"换机器就丢"没有任何实现。
- 举例：`produce-backup-set.sh` 要求 `INPUT_DIR=/tmp/input`、`/tmp/database.pg_dump`、`/tmp/migration-sha.txt`；而 `docs/BACKUP_RESTORE.md` 讲的是 `BRAIN_BACKUP_DEST/PGSERVICEFILE/PGPASSFILE`；`prepare-backup-input.sh` 又把 freeze/thaw 写死 `/home/kms/personal-brain-v1-backup-input`（生产目录是 `-prod-data`）。
- 证据：`deploy/scripts/produce-backup-set.sh:9-46`、`prepare-backup-input.sh:29,35`、`deploy/scripts/backup.sh`、`docs/BACKUP_RESTORE.md`；无 rsync/远端上传实现。
- 严重度：**P1**（灾难恢复链断裂）。
- 断点位置：运维链 → 备份/恢复。

**P1-5 工具业务错误不走 `result.isError`，且 `NOT_FOUND` 与"方法不存在"共用 `-32601`**
- 白话：MCP 规范里"工具执行失败"应当用 `result.isError=true` 在结果里上报；本项目把 `isError` 硬编码为 `False`，所有业务错误一律变成 JSON-RPC 顶层错误 + HTTP 400。同时 `NOT_FOUND` 映射成 `-32601`（协议里"方法不存在"的专用码），客户端会误判为"这个工具不存在"。
- 举例：`create_project(name="   ")` → HTTP 400 `{"code":-32000,"message":"VALIDATION_FAILED"}`（生产实测）；`get_project_context(已删项目)` → `{"code":-32601,"message":"NOT_FOUND"}`（生产实测）。
- 证据：`protocols/mcp_dispatcher.py:97`（硬编码 `isError: False`）、`protocols/remote.py:80-91`（NOT_FOUND→-32601）。
- 严重度：**P1**（互操作：严格按规范解析的客户端会把业务失败当协议故障）。
- 断点位置：协议链 → 响应形态/错误码。

### P2

**P2-1 上传资产的解析文本永不进入检索**
- 白话：上传的文档/图片会被解析成描述文本存进 `derived_contents`，但**没有任何环节给它建检索卡**——用户永远搜不到自己上传的内容。
- 举例：生产库里 62 条 `derived_contents(kind=description)` 是活的，但 209 张检索卡里 `derived_content` 类型为 **0**；`indexer` 没有 asset/derived 分支，`rebuild-index` 也不选资产。
- 证据：`search/indexer.py:65-77`（无 derived 分支）、`infra/assets/derivation.py:44-95`（只写 derived+edges）、`apps/server/personal_brain_server/admin.py:352-363`（rebuild 选择器不含资产）；生产 `search_index_entries` 按 target_type 分组实测。
- 严重度：**P2**（写了不检索，功能够了一半）。断点：摄入链 → 索引。

**P2-2 幂等摘要过窄：同 key 改参数被静默重放**
- 白话：幂等判定只比对 `{operation, 文本, scope}`，所以"同一个 key、改了其它参数"的请求会被当成重试，直接返回旧结果、悄悄忽略你的新参数。
- 举例：`add_todo(content="买菜", priority=1, key=K)` 成功；随后同 key 想改成 `priority=9` → 返回旧结果，priority 仍是 1，且不报 `IDEMPOTENCY_CONFLICT`。`start_task` 的 revision/constraints、`checkpoint_task` 的 next_step、`propose_self_claim` 的 category/policy_class、`create_review_item` 的 item_type 同理；而 `add_expense`/`create_deletion_plan`/`resolve_review_item` 用全量摘要，无此问题——同类工具两种标准。
- 证据：`persistence/authoritative_store.py:84-86`（payload_digest 组成）。
- 严重度：**P2**（静默丢用户意图）。断点：摄入链 → 幂等。

**P2-3 `checkpoint_task`/`finalize_task` 用调用方 scope 授权，与同族工具不一致**
- 白话：项目里 4 个写工具按 `project:<id>` 授权，但任务检查点/收尾这 2 个用的是"调用方自己声明的 scope"——传 `"projects"` 就能命中默认授权，绕过"逐项目授权"。
- 举例：某客户端只有 `project.write@projects`、没有该项目的 `project:<id>`，仍可对已知 task_id 执行 checkpoint/finalize。
- 证据：`api/authorized_tools.py:429-431,536-538`（`scope=requested_scope`）vs `:518-521`、`:409-411`、`:301-311`（`project:<id>`）。
- 严重度：**P2**（授权语义不一致 → 越权窗口）。断点：授权链 → 工具作用域。

**P2-4 answer_brain 的 scope 语义与 search_brain 不同，跨域问答必被拒**
- 白话：`answer_brain` 用 `knowledge.read@<你给的scope>` 授权，而默认客户端只有 `knowledge`；`search_brain` 用的是可跨域的 `search.read`。于是"用财务数据回答问题"这类请求永远 SCOPE_DENIED。
- 证据：`api/authorized_tools.py:263-265` vs `:306-311`；默认清单 `apps/server/personal_brain_server/__main__.py:223-234` + `admin.py` 的默认 grants。
- 严重度：**P2**（能力受限且错误信息不解释）。断点：授权链 → 工具↔默认清单。

**P2-5 删除/复核在内容域默认不可用（真实观感=没权限）**
- 白话：发起删除计划/复核项要用 `review.write@<内容域>`，默认只在 `review` 域有；删 knowledge/finance/projects 的东西必须先运维补 `review-access` 才行。
- 举例：上一轮"手机端建了项目删不掉"就是这个：删除计划报 SCOPE_DENIED，最后是临时 `review-access --scope projects` 才走通。
- 证据：`api/authorized_tools.py:575,628`（`review.write@requested_scope`）；`admin.py:46-52`（作者自注的设计说明）。
- 严重度：**P2**（设计有意，但产品语义上易被当 bug；文档未讲清）。断点：治理链 → 入口授权。

**P2-6 OAuth 令牌会在"创建者自授权"后自失效（潜在 P1，OAuth 上线即触发）**
- 白话：建项目会给创建者补 `project:<id>` 授权并把客户端 epoch +1；而 OAuth 令牌把"发证时的 epoch"烧进令牌并要求与当前 epoch 相等——于是 OAuth 客户端**每建一个项目，自己的令牌立刻失效**，下一次调用 AUTH_INVALID。
- 举例：OAuth 客户端 `create_project` 成功 → 紧接着 `get_project_context` → 401。
- 证据：`security/oauth_grants.py:79,114`（issued_epoch 必须等于 current_epoch）、`infra/security/authority.py` 创建者自授权处的 `permission_epoch + 1`；opaque 凭据每次请求实时读 epoch 所以不受影响（这也是目前手机端没事的原因）。
- 严重度：**P2 潜在 / P1（一旦 T186 走 OAuth 就是首要故障）**。断点：授权链 → epoch 环。

**P2-7 撤销两条路径不对称，留下僵尸 grant**
- 白话：`set_project_access(none)` 只把 scope 从客户端清单里摘掉，授权行仍然"永远有效"；`set_review_access(none)` 反过来收口了授权行却不摘 scope。两种撤销的失效机制不同，项目侧留下僵尸授权行（一旦 scope 被任何路径加回，旧授权立即复活）。
- 证据：`admin.py:251-253`（discard + epoch）vs `:310-315`（effective_to 收口）。
- 严重度：**P2**。断点：授权链 → 运维撤销。

**P2-8 会话是进程内内存态，重启即 401；无 TTL/上限**
- 白话：MCP 会话 id 只存在内存 `set` 里，api 一重启，客户端拿旧 session 继续请求就被判 `AUTH_INVALID` → 401（客户端会误以为是密钥失效）；集合永不清理，长跑缓慢泄漏；多副本/多进程部署直接不可用。
- 证据：`protocols/mcp_dispatcher.py:35,64-65,75-76`；`remote.py:81`（AUTH_INVALID→401）；`__main__.py:279`（单进程 uvicorn，暂未触发多副本问题）。
- 严重度：**P2**。断点：协议链 → 会话管理。

**P2-9 生产编排与仓库不同源**
- 白话：生产用的 `compose.prod.yaml` 不在仓库里（由本机脚本 sed 生成），仓库里另有一个 `compose.override.yaml` 会被 Compose 自动叠加；服务器上文件的组合方式与仓库不可比对，改动容易漂移。
- 证据：`deploy/` 目录实测无 `compose.prod.yaml`；`deploy/windows-local/make_prod_compose.sh`、`deploy/compose.override.yaml:5-18`（`ports: !reset` 需 Compose≥2.24）。
- 严重度：**P2**。断点：部署链 → 编排。

**P2-10 Bridge 契约与离线队列**
- 白话：桥发给服务端的字段名与 `sync_workspace` 要求不一致（`approved_root` vs `approved_root_identity`），且离线队列（`PendingStore`/`offline.py`）没有被入口引用——断网时写请求直接丢弃、无重放。
- 证据：`apps/bridge/client.py:19,38` vs `protocols/tools.py:112-116`、`authorized_tools.py:444-450`；`apps/bridge/__main__.py:27-28`、`stdio.py` 未引用 `pending_store`；`remote_proxy.py:61` 断网抛 `BRAIN_UNAVAILABLE`。
- 严重度：**P2**（桥当前非生产主路径）。断点：桥链 → 契约/离线。

### P3

- **P3-1** LLM 日预算 off-by-one：`> quota` 使得实际允许 `quota+1` 次；且计时器只列 `extract_raw_input/daily_digest`（`worker/llm_budget.py:19,50`）。
- **P3-2** 每日摘要一次最多覆盖 5 个 scope（`digest.py:37,104`），超出的 scope 当天记录被静默排除（结果里 `dropped_scopes` 无人看）。
- **P3-3** `notify_review` 是空壳（`job_handlers.py:113-115` 只返回一条 JSON），复核项无任何推送，只能靠客户端轮询 `list_review_items`。
- **P3-4** 调度无跨日补跑：worker 连续停机 ≥2 天时，中间那天的摘要/演化永久缺失（bucket 保证不重复，也保证不补）。
- **P3-5** 死配置/死 handler：`VERSION_EXEMPT` 里 4 个 `index_project/index_project_task/index_checkpoint/index_workspace_observation` 在生产不存在（核对了全量 job_type）；`provider_derive`、`reprocess_asset` 有 handler 无生产者。
- **P3-6** 索引重写按 `(…, vector_model_version)` 条件删除且表无唯一约束（`search/repository.py:43-49`）——模型不可用窗口内同 target 可并存两张卡（带向量/无向量）。
- **P3-7** `save_note` 的 `content_hash` 去重无唯一约束（`0001:164-178`）：同内容用**新**幂等键重发会新建一行（同 key 有墓碑保护，新 key 不受限）。
- **P3-8** 跨 owner 同文件上传会撞 `uq_asset_blob_identity(sha256,size)`（`0006:70` vs `authoritative_store.py:1080-1083`）→ 500；当前单 owner 部署不可达。
- **P3-9** 日志工具类 `RedactingFilter/CorrelationFormatter/rotation_settings` 无任何调用点（`bootstrap/logging.py:22,38,47`）。
- **P3-10** `db_password`（db 容器初始化）与 `db_dsn`（api/migrate 连接）两处密钥，内容漂移即启动失败且无一致性校验（`deploy/compose.yaml:32,56,90`）。
- **P3-11** 治理闭环缺口（子代理证据，待亲验）：`conflict` 有生产者无处理动作；`ambiguity/permission_change/failed_reconciliation` 无生产者；过期的删除计划不置 expired，永久停在 pending/preview。
- **P3-12** 演化节奏：生产 124 条 B 候选、0 条晋升（晋升要求 ≥3 来源/≥14 天/≥2 上下文，单日导入天然不达标）——"越用越聪明"要 2~3 周后才有可见效果，建议在客户端明示预期（观察项，不是缺陷）。

## 3. 误报与排除（侦探过程记录）

| 疑似 | 排除依据 |
|---|---|
| "今天没有任何调度作业" | 生产本地时间 09-25 00:15，未到 03:10；昨天 18:16 一次性补跑 7 类是部署时点晚于全部时刻的正常行为 |
| 同一天出现 3 次 health_check、2 次 dedupe | bucket 分别是 `probe-2026-09-25`/`after-cleanup`/`post-import`，上一会话手工注入，非幂等失效 |
| 宿主 `cat secrets/db_password` 权限拒绝 | 容器以 root 读只读挂载，宿主属主噪声（与 `server_sql.py` 一致），非启动竞态 |
| 担心 worker/server 向量模型版本不一致 | 生产 209 张卡：208 张 `volcengine:doubao-embedding-vision:1024` + 1 张 NULL（机密内容按设计跳过语义），与代码默认一致 |
| `raw_inputs.original_at` 为空导致摘要漏记录 | 生产实测 NULL = 0 |
| 删除计划级联 / 事实墓碑（上一轮修过的） | 本地 8 项 + 生产 19 项复验全绿，未回退 |

## 4. 覆盖缺口（UNVERIFIED）

- nginx/隧道实机配置（`client_max_body_size`、`proxy_read_timeout`）、手机端是否发 `Origin`、服务器 Compose 版本与叠加形态——仓库内无对应文件可证。
- `tests/security/test_oauth_grant_delegation.py` 覆盖的委托完整性已核对；但**OAuth 端到端**（授权码→令牌→调用）从未在生产跑过（T186 未验收）。
- Bridge 端到端（真实仓库同步）未跑，仅做契约比对。
- `P3-11` 治理闭环三项未亲验（子代理代码证据）。

## 5. 建议处置顺序（待拍板，不擅自修）

1. **P1-1 /doctor 修复**（列名 + 异常不再静默）：观测是你的眼睛，先修它才谈其它。
2. **P1-2 Origin + P1-3 OAuth 资源地址**：决定"要不要开浏览器类客户端 / 何时做 T186"，再定白名单与对外 base URL 的配置化方案。
3. **P1-5 响应形态**：是否把业务错误改为 `200 + isError:true`（会动协议契约，需客户端同步）。
4. **P1-4 备份异机化**：定目标（另一台机器/对象存储）+ 收敛到一套脚本。
5. **P2-1 资产文本入索引**：抽 `derived_content` 的索引分支（含 rebuild-index 覆盖）。
6. 其余 P2 按业务影响排序；P3 可随版本批量清理（死配置/死 handler/日志类）。

## 6. 复现入口

```
# 生产巡检（只读）
uv run python deploy/windows-local/server_sql.py "<SQL>"
# 健康：curl http://192.168.10.7:18083/doctor   （观察 assets/relations=not_checked 即 P1-1）
# MCP 实测（Origin 401 / isError / -32601 复现）
uv run python deploy/windows-local/mcp_probe.py
```