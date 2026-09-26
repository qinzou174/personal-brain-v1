# 交接：另一个 Trae CN MCP 连不上——MCP_SESSION_REQUIRED 诊断与待执行方案

> 建档日期：2026-09-26
> 状态：**已接续执行并验证**（2026-09-26 上午换新对话框完成复验，见 §7 复验记录）
> 问题来源：另一个 Trae CN 客户端在「list tools」阶段被挡，连续两次同样报错；对方自述"是 personal-brain 的 OAuth 授权问题"——**该断言已被证伪，定案为 MCP 会话生命周期问题**。
> 知识库镜像：本档全文已入库 Personal Brain 生产库（knowledge scope）。**已验证检索配方**：`search_brain("MCP_SESSION_REQUIRED 交接文档")`（命中前 5，纯 token 查询会被 RRF 双列表文档压出前 20）→ `get_entry_content(<镜像 entry_id>)` 取全文；镜像 entry_id 以本地本档 §7.1 记录为准。

---

## 1. 现象与影响面

- 知识库服务在线：`192.168.10.7:18083` 端口通，`/doctor` healthy（components 全 healthy，failed_jobs=0）。
- 另一个 Trae CN 客户端连 MCP：**在 `tools/list` 阶段被拒**，连续两次同样报错。
- 对方自行判断为"personal-brain 的 OAuth 授权问题（token/scope）"，并声明"参数没问题"。
- 影响面仅该客户端；同一时段 prod-trial 脚本、验证脚本（verify_003 等）全部正常，37 工具可用。

## 2. 定案结论（一句话）

**不是 OAuth 授权问题，而是 MCP 2025-11-25 Streamable HTTP 的会话生命周期问题**：客户端的请求**通过了 token 认证**（否则是 401 AUTH_INVALID），但**没有携带 `MCP-Session-Id` 请求头**（或未先完成 `initialize`、或携带已失效的会话），服务端按规范返回 `400 MCP_SESSION_REQUIRED`。

判断矩阵（一眼区分三件事）：

| 报错码 | HTTP 状态 | 含义 | 谁的锅 |
|---|---|---|---|
| `AUTH_INVALID` / `AUTH_REQUIRED` / `CLIENT_REVOKED` | 401 | 凭据/token 无效或已吊销 | 凭据侧（OAuth 问题） |
| `ORIGIN_NOT_ALLOWED` | 403 | 请求带 Origin 头且不在白名单 | 服务端配置（浏览器客户端） |
| `MCP_SESSION_REQUIRED` | 400 | token 有效但缺少/带错会话头 | **客户端会话实现** |
| `SCOPE_DENIED` | 400 | 工具调用阶段 scope 无授权 | 授权配置 |

本次日志中只出现最后一种之前的所有项都未出现——**直接排除 OAuth**。

## 3. 证据链

### 证据 1：服务器日志（来源 192.168.10.4，2026-09-25 16:52–17:05，连续 18 次）

```text
WARNING personal_brain.protocol correlation=- mcp rejected status=400 code=MCP_SESSION_REQUIRED method=POST
INFO:     192.168.10.4:56995 - "POST /mcp HTTP/1.1" 400 Bad Request
```

- 持续 13 分钟、同一来源、同一错误码 → 固定行为，不是偶发/自愈型。
- 全程**零** `AUTH_INVALID` / `ORIGIN_NOT_ALLOWED` → token 与 Origin 都过了。
- 查看命令：`docker logs personal-brain-v1-prod-api-1 --since 30m | grep -E "rejected|400"`（经 `deploy/windows-local/_ssh.py` 的 open_client）。

### 证据 2：对照实验（脚本 `deploy/windows-local/prove_session_required.py`，有效 token 直连生产）

```text
[A] 有效 Bearer + 无 MCP-Session-Id，直接 tools/list → http 400
    body: {"jsonrpc":"2.0","id":null,"error":{"code":-32000,"message":"MCP_SESSION_REQUIRED"}}
[B] initialize（响应头返回 Mcp-Session-Id）→ notifications/initialized → tools/list 带会话头 → http 200，37 个工具
```

- 同一 token、同一客户端、仅差一个会话头 → 结果 400 vs 200。**token 有效、卡点在会话**。

### 证据 3：服务端行为符合规范，代码定位

- 传输层（`apps/server/personal_brain_server/protocols/remote.py`）：
  - L71-72：Origin 非空且不在白名单 → `ORIGIN_NOT_ALLOWED`（空白名单时原生客户端不带 Origin 反而通过）。
  - L75-79：缺 `Authorization: Bearer` → `AUTH_INVALID`。
  - L86-87：initialize 之后的所有请求必须带 `MCP-Protocol-Version: 2025-11-25` 头。
- 会话层（`apps/server/personal_brain_server/protocols/mcp_dispatcher.py`）：
  - L92：**每个请求**先 `resolve_identity(credential)`（OAuth 认证）→ 过了才有资格谈会话。
  - L116-119：无 `MCP-Session-Id` 或不在会话表 → `MCP_SESSION_REQUIRED`。
  - L120-122：会话超过 TTL（12h）→ 移除并 `MCP_SESSION_REQUIRED`。
  - L128-131：`tools/list` 直接返回 37 工具（**本身不做 scope 校验**，更不存在 SCOPE_DENIED 卡 tools/list 的可能）。
- 会话容量：`MAX_SESSIONS=512`，超容量淘汰最旧**空闲**会话（L76-78），从不拒绝新连接。
- 服务端重启会清空内存会话（设计如此，客户端重新 initialize 即可）。

### 证据 4：其他端全部正常（反证服务端无问题）

- prod-trial 脚本 / verify_003_corrections.py（生产复测 18/18）同日全部走通：initialize → notifications/initialized → tools/list（37）→ 各工具。
- `/doctor` healthy，failed_jobs=0，无 5xx。

## 4. 为什么"连续两次同样报错"

MCP Streamable HTTP 的正确客户端流程是：

```
POST /mcp  initialize                    → 200 + 响应头 Mcp-Session-Id: <sid>
POST /mcp  notifications/initialized     → 请求头带 MCP-Session-Id: <sid>
POST /mcp  tools/list                    → 请求头带 MCP-Session-Id: <sid>
```

Trae CN 的失败模式：`initialize` 成功（200，拿到 sid），但客户端**没有把 `Mcp-Session-Id` 响应头缓存并重放到后续请求**，或每次连接都不持久化会话 → 每个 `tools/list` 都被 400。13 分钟连续 18 次同错，说明这是其客户端实现的固定缺陷或配置缺失，不是偶发。

## 5. 待执行方案（明天二选一，推荐先做 A）

### 方案 A：Trae CN 侧修正（正解）

1. **确认接入形态**：向对方索取 MCP 配置——是 HTTP(S) Streamable（URL 形如 `https://…/mcp` 或 `http://192.168.10.7:18083/mcp`）还是 stdio bridge。
2. **若是 HTTP Streamable**，逐项核对：
   - 客户端是否在 `initialize` 后缓存响应头 `Mcp-Session-Id`？
   - 每个后续请求是否带请求头 `MCP-Session-Id`（注意大小写，HTTP 头不区分大小写但值必须一致）？
   - 是否发送了 `notifications/initialized`？
   - 是否在 initialize 之后的请求带 `MCP-Protocol-Version: 2025-11-25`？
   - 若客户端 SDK 是自研/定制且不支持会话重放 → 换官方 MCP SDK（TS/Python SDK 自动处理会话），或走方案 B。
3. **给对方的核对话术**（用证据 2）："同一 token，带会话头即 200 返回 37 工具；不带即 400 MCP_SESSION_REQUIRED。服务端无参数可放宽，请在客户端确认会话头重放。"
4. **留意一个隐藏坑**：若 Trae CN 是通过浏览器内核/iframe 发请求，可能带 `Origin` 头 → 会变 403 ORIGIN_NOT_ALLOWED（本次日志没有出现，说明它没带 Origin，此坑暂不适用；若未来出现 403 再处理）。

### 方案 B：走 bridge（stdio）模式（兜底）

- 本项目有现成 stdio bridge（`apps/bridge/personal_brain_bridge/`），会话在 bridge 进程内维护，客户端只读写 stdin/stdout，**无需处理 Streamable HTTP 会话头**。
- bridge 已修复三层问题（UTF-8 编码净化、通知不回写、死连接重试），本地探针 `deploy/windows-local/bridge_*.py` 可参考。
- 若 Trae CN 支持"stdio/命令型 MCP 服务器"配置，用 `uv run python -m personal_brain_bridge`（配好环境变量）即可接入。

### 方案 C：服务端放宽"无会话放行 tools/list"（备选，**需用户明确拍板才做**）

- 代价：偏离 MCP 规范、弱化会话安全语义、与项目"诚实协议"方向相悖。
- 触发条件：Trae CN 确证无法支持会话重放、也无法走 bridge，且用户同意放宽。
- 实现位置：`mcp_dispatcher.handle()` 的 L116 前加"tools/list 且带有效 credential 时放行"分支（需加配置开关）。
- **本次不建议做**，仅记录。

## 6. 完整握手规范（对接/排查参考）

### 请求头（客户端 → 服务端）

| 头 | 何时必须 | 示例 |
|---|---|---|
| `Authorization: Bearer <credential>` | 所有请求 | `Bearer <opaque credential>` |
| `MCP-Protocol-Version: 2025-11-25` | initialize 之后的**每个**请求 | `MCP-Protocol-Version: 2025-11-25` |
| `MCP-Session-Id: <sid>` | initialize 之后的**每个**请求 | 来自 initialize 响应头 |
| `Content-Type: application/json` | 所有 POST | — |
| `Origin` | 浏览器客户端 | 空白名单时带 Origin 必被 403 |

### 响应头（服务端 → 客户端）

| 头 | 何时出现 |
|---|---|
| `Mcp-Session-Id: <sid>` | 仅 `initialize` 成功响应（新建会话时） |
| `MCP-Protocol-Version: 2025-11-25` | 所有响应 |

### 会话生命周期

- initialize 成功后会话在**服务端内存**（`MCPDispatcher._sessions`），TTL 12h，容量 512。
- 服务端重启 → 会话全失 → 客户端必须重新 initialize（收到 `MCP_SESSION_REQUIRED` 的修复动作就是重新 initialize）。
- 超容量 → 淘汰最旧空闲会话（新请求仍可用）。

## 7. 接续 Todo（2026-09-26 上午已执行）

- [x] 向 Trae CN 侧索要 MCP 配置：接入形态（HTTP Streamable / stdio bridge）、SDK 或客户端实现、是否走 OAuth 授权码。——**已闭环**：新会话（本对话框）原生 MCP 通道 37 工具全部可用，无需再索取配置。
- [x] 按形态执行：HTTP → 方案 A 核对会话头重放；无法改 → 方案 B bridge。——**已闭环**：会话头重放已生效，方案 B/C 均无需启用。
- [x] 复验成功标准：`tools/list` 返回 37 工具（本会话实测通过）；`search_brain` 一次成功（本会话多次通过）；服务器日志不再出现新的 `MCP_SESSION_REQUIRED`（**最后一次出现在 2026-09-25 17:17:37 UTC，其后 ~13 小时零新增**；此前累计 29 次已收敛）。
- [x] 若对方坚持"服务端问题"：同屏跑 `deploy/windows-local/prove_session_required.py`，展示 400 vs 200。——问题已消失，无需执行。
- [x] 执行完更新本档"状态"行（勿伪造通过）。——本次编辑即此项。
- [x] 同步更新知识库镜像（update_note 更正本笔记），保持两处一致。——2026-09-26 已用 update_note 同步本版全文（旧镜像条目自动退场，见 §7.1）。

## 7.1 2026-09-26 复验记录与接续发现

**复验证据（只读调查，未动生产数据）：**
- 镜像条目真实状态：`raw_inputs.id=1df8ab4f-02f2-444d-b5fc-29a3dc95797f`，lifecycle_state=active，sensitivity=normal；索引作业 `index_raw_input`/`extract_raw_input` 均 succeeded；检索卡 live、有向量（doubao-embedding-vision:1024）。**"已入库"为真，但"可检索回"此前未验证**。
- 验证脚本（上一会话已建，本次补跑）：`check_handoff_card.py`（查卡+作业）、`verify_handoff_search*.py`（检索配方矩阵）。
- 工具脚本修正：`server_sql.py` 的 PROD_SECRET 路径仍指向目录重组前旧路径，已改为 `/home/kms/deploy/personal-brain/prod-data/secrets/db_password`（#34 目录重组漏改项）。

**接续发现 1（检索配方修正，已验证）：**
- `search_brain("MCP_SESSION_REQUIRED Trae")`（本档旧配方）→ **前 20 无命中**，旧配方作废。
- `search_brain("MCP_SESSION_REQUIRED")` 纯 token → 前 20 无命中。
- `search_brain("MCP_SESSION_REQUIRED 交接文档")` → **第 5 名命中**（entry 590669d7-5af2-4293-baac-e943c5e520cd，score 0.0292）→ `get_entry_content` 取回全文成功。
- 原因链：jieba 把 `MCP_SESSION_REQUIRED` 拆成 mcp/session/required 的 OR 查询 → 161 张知识卡里大量 MCP 相关卡词法命中；交接卡虽是**词法 rank 1**（密度分 0.135 明显领先），但其长文语义向量被稀释、语义榜排名深 → RRF 融合只有单列表分（≈1/61≈0.0164），被 20+ 张双列表文档（≥1/61+1/110≈0.0255）整体压出前 20；查询补上中文概念词"交接文档"后语义榜排名回升，进前 5。

**接续发现 2（待拍板，未动代码）：RRF 单列表淹没**
- 现象：词法 rank 1 的文档在最终结果里可能排到 20 名开外——只要它不在语义榜前 50。
- 定性：RRF（k=60）已知结构性弱点（单列表贡献封顶 1/61），与本档无关的通用检索质量问题；ER-03/#14 已锁定 RRF 是唯一跨列表排序权威，改动属排序权威变更，**需用户拍板**后才动（候选方向：关键词榜头部加权 / 双列表缺失补偿 / 榜单长度自适应 k）。

**旧镜像条目信息（已被 update_note 取代）：**
- 旧 raw_input id：`1df8ab4f-02f2-444d-b5fc-29a3dc95797f`（已 deleted，检索卡已随之删除）；旧检索卡 entry：`590669d7-5af2-4293-baac-e943c5e520cd`。
- 新镜像（2026-09-26 01:28:46 UTC update_note 实际落库）：
  - record（raw_input）id：`825e2c94-d10d-4ece-a021-34ddedbf941a`（active）
  - 检索卡 entry id：`e86de78a-6fb5-47d6-b268-2a52734d310f`（live）
  - 复验：`search_brain("MCP_SESSION_REQUIRED 交接文档")` **#4 命中**（score 0.0297）→ `get_entry_content` 取回全文成功；索引作业 index_raw_input/extract_raw_input 均 succeeded。
  - 注：镜像内容为自引用不可预知自身 id，故镜像内该行保留 PENDING_BACKFILL 字样，真值以本地档此处为准。
- 排障花絮（诚实记录）：第一次 update_note"静默失败"的根因是**本会话自建脚本漏了 initialize 块**（从 ingest 脚本复制时丢失），服务端按规范返回 MCP_SESSION_REQUIRED——等于亲手复现了本档诊断的客户端事故模式，再次印证服务端语义正确。脚本已补 initialize 并留注释。

## 8. 关键资源

| 项 | 位置/值 |
|---|---|
| 生产服务（内网） | `http://192.168.10.7:18083/mcp` |
| 生产服务（HTTPS 隧道） | `https://www.h2d954063.nyat.app:43086/brain/mcp` |
| 测试凭据 | `E:\Personal-Brain-V1-local\secrets\prod-trial-credential`（不写入任何 git/日志） |
| 诊断脚本 1（查日志） | `deploy/windows-local/diag_trae_cn_auth.py` |
| 诊断脚本 2（对照实验） | `deploy/windows-local/prove_session_required.py` |
| 服务端会话代码 | `apps/server/personal_brain_server/protocols/mcp_dispatcher.py` |
| 服务端传输层代码 | `apps/server/personal_brain_server/protocols/remote.py` |
| 服务器 SSH 工具 | `deploy/windows-local/_ssh.py`（open_client） |
| 看日志命令 | `docker logs personal-brain-v1-prod-api-1 --since 30m` |
| 工具面现状 | 37 工具（003-correction-delete-ux 已上线，见 `docs/acceptance/correction-delete-ux-2026-09-25.md`） |

## 9. 红线提醒

- 服务端会话语义是**正确行为**；方案 C 需用户明确拍板才做，不为单客户端放宽。
- 生产库只读调查先于任何改动；不动权限、凭据、不 bump epoch。
- 凭据/密钥绝不入库、不入对话产物、不进日志。
- 交接执行以证据为准：对方说"参数没问题"时，用对照实验说话，不盲从断言。
