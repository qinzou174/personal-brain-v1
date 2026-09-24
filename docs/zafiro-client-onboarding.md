# Zafiro 客户端接入文档

> **更新日期**：2026-09-24
> **服务端**：Personal Brain V1（局域网生产实例，`192.168.10.7`）
> **协议**：MCP（Model Context Protocol）over Streamable HTTP（JSON-only）

---

## 1. 连接参数

| 项 | 值 |
|---|---|
| Endpoint | `http://192.168.10.7:18081/mcp` |
| 传输 | `POST` + `application/json`（不支持 GET / SSE 探测，`GET /mcp` 返回 405 属正常） |
| 认证头 | `Authorization: Bearer <TOKEN>` |
| 版本头 | `MCP-Protocol-Version: 2025-11-25`（initialize **之后**的请求必需） |
| 会话头 | `MCP-Session-Id`（从 initialize 响应头取得，后续请求原样回带） |
| 网络前提 | 与 `192.168.10.7` 同一局域网 |

**凭据获取**：token 不在此文档中明文保存，只存在服务端文件：

```bash
ssh codex-kms "cat /home/kms/personal-brain-v1-data/secrets/zafiro-credential"
```

token 是 64 字符 bearer 串，只应在客户端本地安全存储（密钥库/`chmod 600` 文件），不要写入聊天、日志或版本库。

---

## 2. 客户端身份与授权

| 项 | 值 |
|---|---|
| client_id | `a567a812-8363-4fae-ab8c-95f4aee31132` |
| client_type | `mobile` |
| status | `active` |
| permission_epoch | `2`（写权限已启用，见 §6） |
| 授权行数 | 22 条（`owner_local_operator` 签发，`sensitivity_ceiling=private`） |

### 2.1 授权矩阵（来自库内 `permission_grants`，2026-09-24 核实）

| 工具 | knowledge | finance | todo | self | asset | projects |
|---|---|---|---|---|---|---|
| `search.read` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `context.read` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `knowledge.read` | ✅ | — | — | — | — | — |
| `knowledge.write` | ✅ | — | — | — | — | — |
| `finance.read` | — | ✅ | — | — | — | — |
| `finance.write` | — | ✅ | — | — | — | — |
| `todo.read` | — | — | ✅ | — | — | — |
| `todo.write` | — | — | ✅ | — | — | — |
| `self.read` | — | — | — | ✅ | — | — |
| `self.write` | — | — | — | ✅ | — | — |
| `asset.write` | — | — | — | — | ✅ | — |
| `project.write` | — | — | — | — | — | ✅ |

**未授予**（请求会返回 `SCOPE_DENIED`，属正确行为，不要重试）：

- `diary` 作用域（所有客户端均未开放）
- `operations` / `review` 作用域
- 项目级精确授权（`project.read:<id>` / `project.write:<id>`）—— 项目工具需要精确到具体 project_id 的授权（见 §5 备注）

---

## 3. MCP 握手流程（严格按序，一次一个请求）

### 3.1 initialize

```bash
curl -sS -D /tmp/zaf_h -o /tmp/zaf_b -X POST "http://192.168.10.7:18081/mcp" \
  -H "Authorization: Bearer $(cat <credential-file>)" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"zafiro","version":"1"}}}'
```

- 成功：`200`，响应头含 **`MCP-Session-Id`**（必须保存，后续每个请求回带）
- `result.protocolVersion` 服务端固定返回 `2025-11-25`（请求版本不同则以服务端返回为准）
- 服务端 `serverInfo.name` = `personal-brain`

### 3.2 notifications/initialized

```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "http://192.168.10.7:18081/mcp" \
  -H "Authorization: Bearer $(cat <credential-file>)" \
  -H "MCP-Session-Id: <会话id>" \
  -H "MCP-Protocol-Version: 2025-11-25" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'
```

- 期望 `202` 且响应体为空 —— 这是正常现象，不是错误

### 3.3 tools/list

```bash
curl -sS -X POST "http://192.168.10.7:18081/mcp" \
  -H "Authorization: Bearer $(cat <credential-file>)" \
  -H "MCP-Session-Id: <会话id>" \
  -H "MCP-Protocol-Version: 2025-11-25" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

- `200`，返回 30 个工具定义；每个工具的 `inputSchema` 是调用的权威参数来源

---

## 4. 可用的 MCP 工具（读）

> 业务结果在 `result.structuredContent`（JSON 对象）；`result.content[0].text` 是它的 JSON 字符串形式。

| 工具 | 契约工具 | 作用域 | 说明 |
|---|---|---|---|
| `get_brain_context(intent, requested_scope)` | `context.read` | 6 个内容作用域 | 指定作用域总览上下文 |
| `search_brain(query, requested_scope, [sensitivity_ceiling], [limit])` | `search.read` | 6 个内容作用域 | 模糊/语义检索 |
| `answer_brain(query, requested_scope)` | `knowledge.read` | knowledge | 基于知识库的问答（会调用外部模型，可能较慢） |
| `get_self_context(categories, requested_scope)` | `self.read` | self | 个人画像 |
| `get_expense_summary([currency], requested_scope)` | `finance.read` | finance | 支出汇总 |
| `list_expense_records(requested_scope)` | `finance.read` | finance | 支出明细 |
| `list_todos(requested_scope)` | `todo.read` | todo | 待办清单 |

> **注意**：`search_brain` / `get_brain_context` 的结果被限制在客户端实际持有的作用域集合内，检索不会越过授权边界；未授权作用域在访问索引前即返回 `SCOPE_DENIED`。

## 5. 可用的 MCP 工具（写）

| 工具 | 契约工具 | 作用域 | 说明 |
|---|---|---|---|
| `save_note(content, requested_scope, idempotency_key)` | `knowledge.write` | knowledge | 存笔记 |
| `add_todo(content, requested_scope, idempotency_key, [priority])` | `todo.write` | todo | 加待办 |
| `complete_todo(todo_id, expected_version, idempotency_key)` | `todo.write` | todo | 完成待办 |
| `add_expense(amount, currency, category, description, occurred_timezone, requested_scope, idempotency_key)` | `finance.write` | finance | 记支出 |
| `propose_self_claim(claim, category, ...)` | `self.write` | self | 提议个人画像声明 |
| `upload_asset(..., requested_scope, idempotency_key)` | `asset.write` | asset | 上传资料 |

> **备注**：项目类工具（`create_project` / `start_task` / `record_decision` 等，契约 `project.write`）虽然已授予 `projects` 作用域级 `project.write`，但项目工具在精确授权模型下需要**针对具体 project_id** 的授权行（`project.write:<id>`）。当前 Zafiro **未配置任何具体项目的精确授权**，调用这些工具会返回 `SCOPE_DENIED`。如需开放某个项目，由 owner 执行：

```bash
docker compose exec -T api python -m personal_brain_server project-access \
  --client-id a567a812-8363-4fae-ab8c-95f4aee31132 \
  --project-id <project_id> --access write \
  --confirm-client-id a567a812-8363-4fae-ab8c-95f4aee31132 \
  --confirm-project-id <project_id>
```

---

## 6. 调用约定

- **`requested_scope` 取值**：`knowledge` / `finance` / `todo` / `self` / `asset` / `projects`。`diary` 未开放，请求返回 `SCOPE_DENIED`。
- **`sensitivity_ceiling`**：默认 `private`，一般无需传；仅当用户明确要求不同隐私级别时调整。
- **幂等（重要）**：所有写操作必须携带 `idempotency_key`（UUID）。**网络重试时必须复用同一个 key**，否则会重复写入；服务端按 `(client_id, operation, idempotency_key)` 去重，重放返回首次结果。
- **`complete_todo` 的 `expected_version`**：用 `list_todos` 返回的 `version` 字段；不匹配返回 `VERSION_CONFLICT`。
- **时区/货币**：默认 `Asia/Shanghai`、`CNY`。
- **结果确认**：写操作成功后，可用对应读操作复核（如 `add_todo` 后 `list_todos`）。

---

## 7. 错误判读

| HTTP | 含义 | 处理 |
|---|---|---|
| 401 | 凭据无效 / 被吊销 / 版本不匹配 | 停止重试，联系 owner 轮换凭据 |
| 400 | 格式或业务校验失败 | 读 `error.message`：`SCOPE_DENIED` / `VALIDATION_FAILED` / `NOT_FOUND` / `VERSION_CONFLICT` |
| 405 | 用了 GET | 改用 POST（GET 不支持，不是故障） |
| 202 | notification 的正常响应 | 无需处理 |

**错误响应体结构**：`{"jsonrpc":"2.0","id":null,"error":{"code":-32000,"message":"<错误码>"}}`。

---

## 8. 凭据生命周期

- **轮换**（旧凭据立即失效）：

```bash
docker compose exec -T api python -m personal_brain_server rotate-client \
  --client-id a567a812-8363-4fae-ab8c-95f4aee31132 --credential-file <path>
```

- **吊销**（客户端彻底不可用）：

```bash
docker compose exec -T api python -m personal_brain_server revoke-client \
  --client-id a567a812-8363-4fae-ab8c-95f4aee31132 \
  --confirm-client-id a567a812-8363-4fae-ab8c-95f4aee31132
```

- 轮换后 token 值变化，需重新从服务端凭据文件取出（见 §1），旧 token 立即返回 401。

---

## 9. 安全注意事项

1. **token 是敏感凭据**：只存客户端本地安全位置，不落日志、不进聊天、不进版本库。
2. **写操作有幂等保护**：不要自己生成"重试用的新 key"，同一操作重试必须复用原 key。
3. **作用域边界由服务端强制**：即使客户端发起越界 scope 请求，服务端也会在访问索引/数据前拒绝。
4. **隐私分级**：本客户端授权 `sensitivity_ceiling=private`，即默认只读写 `private` 及以下密级内容。
5. **日志监听**：服务端拒绝类请求会以无正文形式记录（`mcp rejected status=... code=...`），不包含请求体与凭据。
