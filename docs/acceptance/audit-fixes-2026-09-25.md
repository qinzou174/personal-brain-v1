# Chain-Audit 修复验收（2026-09-25，五批推进）

> 上游证据：`docs/acceptance/chain-audit-2026-09-25.md`（5×P1 + 10×P2 + 12×P3）。
> 用户拍板：全部按推荐顺序执行。本文件按批次记录修复、验证与遗留。

## 批次总览

| 批 | 内容 | 提交 | 验证 |
|---|---|---|---|
| 1 协议与观测 | doctor 真检查、Origin 可配+403、OAuth 公网基址、in-band 工具错误、NOT_FOUND 独立码、会话 TTL/上限、compose.prod.yaml 入库 | `cda4f36` | 本地 572 passed；生产 `/doctor` 三项 healthy、发现端点回隧道地址、协议探针 6/7（唯一 FAIL 为探针自身预期错） |
| 2 备份异机化 | `prod-backup.sh`（dump+数据根+密钥，openssl 加密）+ `pull_backup.py`（拉回+校验） | `a928f6f`/`2b807e3`/`9f0c8c5` | 生产实跑生成 1.6MB 包；5 项 sha256 全过；`pg_restore --list` 257 项有效；本机副本校验一致 |
| 3 检索与授权 | 上传文本入索引（parse→index_derived_content→卡 + rebuild 覆盖）、任务按项目授权、answer_brain 用 search.read、创建者自授权不再 bump epoch、项目撤销收口 grant 行、空白源声明式跳过 | `da3940b`/`04eee68` | 全量 578 passed；生产 rebuild 350+ 作业、资产卡出现且 search_brain(scope=asset) 命中；外部客户端写他人项目 SCOPE_DENIED；answer_brain(finance) 不再 SCOPE_DENIED |
| 4 幂等与杂项 | 幂等摘要带区分参数（priority/revision/policy_class/item_type/...→IDEMPOTENCY_CONFLICT）、LLM 预算 off-by-one、bridge 字段对齐服务端 schema、日志脱敏/相关性格式化真正接线 | 见 git log | 本地聚焦 62 passed |
| 5 回归+文档 | 全量回归 + 本文档 | — | 见下 |

## 关键行为变化（客户端可见）

1. **工具失败**：`HTTP 200 + result.isError=true + structuredContent.code`（原为 HTTP 400 顶层 error）。严格客户端按 MCP 规范处理 isError 即可。
2. **错误码**：`NOT_FOUND` → `-32004`（原 `-32601` 与"方法不存在"共码）；未知方法仍是 `-32601`。
3. **Origin 被拒**：`403 ORIGIN_NOT_ALLOWED`（原 401，会被误读为凭据失效）。放行浏览器类客户端：`BRAIN_ALLOWED_ORIGINS=https://app.example.test`。
4. **丢失会话**：`400 MCP_SESSION_REQUIRED`（原 401 AUTH_INVALID）——客户端应重新 initialize 而非轮换凭据。会话 12 小时过期、上限 512 个。
5. **OAuth 发现/受众**：`/.well-known/oauth-protected-resource` 现回 `https://www.h2d954063.nyat.app:43086/brain/mcp`（`BRAIN_PUBLIC_BASE_URL` 配置）。
6. **同步语义**：同幂等键不同参数 → `IDEMPOTENCY_CONFLICT`（原静默返回旧结果）。
7. **权限**：`checkpoint_task`/`finalize_task` 授权改由任务所属项目决定（`requested_scope` 不再是授权输入）；`answer_brain` 用 `search.read`（跨域问答可用）。
8. **运维**：`/doctor` 真检查资产/关系（损坏/断裂会出现 failed + findings）；`BRAIN_ALLOWED_ORIGINS`/`BRAIN_PUBLIC_BASE_URL` 加入 Settings（`extra="forbid"` 注意 compose 需同步）。

## 生产编排

`deploy/compose.prod.yaml` 已入库（含 `BRAIN_PUBLIC_BASE_URL`），服务器上的生成版已删除、
`compose.override.yaml` 更名为 `.superseded` 停用——仓库与生产单源。部署命令见文件头注释。

## 备份与恢复（已实证）

```bash
# 服务器（每次部署后/每日 cron 建议）
deploy/scripts/prod-backup.sh
# 本机异机副本（sha256 校验 + 保留最近 5 份）
uv run python deploy/windows-local/pull_backup.py
```
恢复流程与已验证的 `pg_restore --list` 证据见 `docs/BACKUP_RESTORE.md` 顶部。
`~/.brain-backup-passphrase`（服务器，600）必须与备份分开保存。

## 回归

最终全量（批 4 后）：**580 passed / 12 skipped / 0 failed**（批次 1-3 分别为 572/578 passed）。

## 遗留（未做，需另行拍板）

| 项 | 说明 | 建议 |
|---|---|---|
| 治理闭环缺口（P3-11） | `conflict` 型复核项批准后 conflicts 行不闭合；`ambiguity/permission_change/failed_reconciliation` 无生产者；过期删除计划不置 expired | 单独一批治理工作 |
| Bridge 离线队列未接线 | `PendingStore` 仍无入口引用（字段契约已对齐） | Bridge 启用时做 |
| write-after-delete | record_decision/start_task/sync_workspace 仍可对墓碑项目写行（检索侧已封死） | 与治理批一起 |
| nginx/隧道实机配置 | `client_max_body_size`、`proxy_read_timeout` 未核实 | 有网络层症状时查 |
| digest 每日 5 scope 上限、调度不补跨日 | P3 观察项 | 数据量上来后再议 |
