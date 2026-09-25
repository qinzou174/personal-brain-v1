# 交接：另一个 Trae CN MCP 连不上——MCP_SESSION_REQUIRED 诊断与待执行方案

> 建档日期：2026-09-26
> 状态：**诊断完成，待执行**（用户将于明日换对话框执行）
> 问题来源：另一个 Trae CN 客户端在「list tools」阶段被挡，连续两次同样报错；对方自述"是 personal-brain 的 OAuth 授权问题"——**该断言已被证伪**。

## 1. 现象

- 知识库服务在线：`192.168.10.7:18083` 端口通，/doctor healthy。
- 另一个 Trae CN 客户端连 MCP，在 `tools/list` 阶段被拒绝，连续两次同样报错。
- 对方判断为"OAuth 授权问题"（`AUTH_INVALID`/`SCOPE_DENIED` 之类）。

## 2. 诊断结论（证据链，已定案）

**根因不是 OAuth 授权，而是 MCP Streamable HTTP 会话生命周期问题**：客户端请求通过了 token 认证，但**没有携带 `MCP-Session-Id` 头**（或未先完成 initialize / 带的是已失效会话），服务端按规范返回 `MCP_SESSION_REQUIRED`。

### 证据 1：服务器日志（192.168.10.4，2026-09-25 16:52–17:05，连续 18 次）

```
WARNING personal_brain.protocol mcp rejected status=400 code=MCP_SESSION_REQUIRED method=POST
```

- 全部是 400 `MCP_SESSION_REQUIRED`；**从未出现** `AUTH_INVALID`/`SCOPE_DENIED`。
- 若真是 OAuth/token 问题，传输层会先返回 401 `AUTH_INVALID`（见 `apps/server/personal_brain_server/protocols/remote.py` 的 `_HTTP_STATUS`）。

### 证据 2：对照实验（`deploy/windows-local/prove_session_required.py`，有效 token 直连生产）

```
[A] 有效 Bearer + 无 MCP-Session-Id，直接 tools/list → 400 MCP_SESSION_REQUIRED
[B] 先 initialize（响应头返回 Mcp-Session-Id）→ tools/list 带上会话头 → 200，37 个工具
```

- 同一 token，仅差一个会话头，结果截然不同 → 证明 token 有效、卡点在会话。

### 证据 3：服务端行为符合 MCP 2025-11-25 规范，其他端正常

- `tools/list` 前强制会话：`apps/server/personal_brain_server/protocols/mcp_dispatcher.py` L116-122（`MCP_SESSION_REQUIRED`）。
- 会话容量 512、TTL 12h；超容量只淘汰最旧空闲会话，不拒绝新连接。
- 同一时间段 prod-trial 脚本/验证脚本全部正常（37 工具、18/18 复测通过）。

## 3. 为什么"连续两次同样报错"

Trae CN 客户端的典型失败模式：每次请求对（initialize 成功 → 后续 tools/list）中，客户端没有把 `initialize` 响应头的 `Mcp-Session-Id` 缓存并重放到后续请求 → 每个 tools/list 都被 400。持续 13 分钟说明它不是"重启一次能自愈"的偶发，而是客户端实现/配置层面的固定行为。

## 4. 待执行方案（明天二选一，建议先做 A）

### 方案 A：Trae CN 侧修正（正解，推荐）

1. 确认 Trae CN 的 MCP 接入形态：是 **HTTP(S) Streamable**（URL `https://…/mcp`）还是 **stdio bridge**。
2. 若为 HTTP Streamable：
   - 检查其 MCP 客户端是否遵循会话语义——`initialize` 后必须缓存响应头 `Mcp-Session-Id`，并在每个后续请求带 `MCP-Session-Id` 头（注意大小写：请求头 `MCP-Session-Id`）。
   - 若 Trae CN 用的是自研/定制 MCP 客户端且不支持会话重放，优先换用标准 MCP SDK（官方 TS/Python SDK 会自动处理会话），或用方案 B。
3. 若对方仍坚持"参数没问题"，把本文档证据 2 的对照实验结果发它，并说明：**同一 token、带会话头即 200**，服务端无可放宽项。

### 方案 B：走 bridge（stdio）模式（兜底）

本项目有现成 stdio bridge，会话在 bridge 内部维护，客户端只需读写 stdin/stdout，无需处理 Streamable HTTP 会话头。之前 Trae 原生通道即以此方式修通。参考：
- `apps/bridge/personal_brain_bridge/`（`__main__.py` 已修复 UTF-8 编码/通知/死连接三层问题）
- 配置形态与本地探针见 `deploy/windows-local/bridge_*.py`

### 方案 C（备选，需用户拍板，本次**不**建议做）

服务端放宽"无会话放行 `tools/list`"（只读发现）。代价：偏离 MCP 规范、弱化会话安全语义，且与 B-系列历史修复方向相悖。除非 Trae CN 确实无法支持会话且无法走 bridge，否则不做。

## 5. 关键资源

| 项 | 位置/值 |
|---|---|
| 生产服务 | `192.168.10.7:18083`（/doctor healthy，容器 api/worker/model-proxy/db） |
| 测试凭据 | `E:\Personal-Brain-V1-local\secrets\prod-trial-credential` |
| 诊断脚本 | `deploy/windows-local/diag_trae_cn_auth.py`（查服务器日志）、`deploy/windows-local/prove_session_required.py`（对照实验） |
| 服务端会话代码 | `apps/server/personal_brain_server/protocols/mcp_dispatcher.py`、`protocols/remote.py` |
| 服务器 SSH | `deploy/windows-local/_ssh.py`（open_client）；查看日志：`docker logs personal-brain-v1-prod-api-1 --since 30m` |
| 既有验收 | `docs/acceptance/correction-delete-ux-2026-09-25.md`（工具面 37，生产复测 18/18） |

## 6. 明天接续 Todo

- [ ] 向 Trae CN 侧索要其 MCP 配置（URL 形态 / 是否走 OAuth 授权码 / SDK 版本）
- [ ] 按其形态执行方案 A（会话头重放确认）或方案 B（bridge）
- [ ] 复验：`tools/list` 返回 37 工具；`search_brain` 一次成功（日志无 MCP_SESSION_REQUIRED）
- [ ] 若对方仍无法连接，回看本文档证据 2，必要时与对方同屏复现
- [ ] 执行完成与否，在本档"状态"行更新，勿伪造通过

## 7. 红线提醒

- 服务端会话语义是正确行为，**不要为单客户端放宽**（方案 C 需用户明确拍板才做）。
- 生产库只读调查先于任何改动；不动权限/凭据。
- 凭据/密钥不入库、不入对话产物。
