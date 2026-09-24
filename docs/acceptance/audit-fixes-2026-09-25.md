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
| ~~治理闭环缺口（P3-11）~~ | ~~`conflict` 型复核项批准后 conflicts 行不闭合；无生产者死类型；过期删除计划不置 expired~~ | **已在批 6 修复**（见下） |
| Bridge 离线队列未接线 | `PendingStore` 仍无入口引用（字段契约已对齐） | Bridge 启用时做 |
| ~~write-after-delete~~ | ~~record_decision/start_task/sync_workspace 仍可对墓碑项目写行~~ | **已在批 6 修复**（见下） |
| nginx/隧道实机配置 | `client_max_body_size`、`proxy_read_timeout` 未核实 | 有网络层症状时查 |
| ~~digest 每日 5 scope 上限~~ | ~~超过 5 个作用域的摘要被静默截断~~ | **已在批 6 修复**（见下） |
| digest 调度不补跨日 | 错过 03:10 窗口的当日摘要不会补算 | 数据量上来后再议 |

---

# 批 6：治理闭环、墓碑写门禁、通知送达、digest 全量（2026-09-25）

> 上游：用户拍板"值得修的 5 条"（白话解释中的 ①-⑤）。本批全部落码并配集成测试。

## 修复内容

**① 治理闭环（原 P3-11）**
- `resolve_review_item` 新增 `conflict` 分支：批准 → conflicts 行置 `resolved_by_user`；拒绝 → 置 `tolerated`。participants 与库内比对不一致返回 `CONFLICT_MISMATCH`，防止裁决错行。
- `evolution.conflict_scan` 的 known_pairs 合并 conflicts 表所有非 open 行的 participants——**裁决过的对永不重新生成**（原缺陷：批准后下一轮扫描又生成同样的 conflict，死循环刷 Inbox）。
- 过期删除确认改为**终态提交**：原来抛 `CONFIRMATION_EXPIRED` 事务回滚，item 永远 open、每天重复提醒；现在关闭 item（resolved）、plan 置 `confirmation_state=expired`、写 audit、返回 `{"status": "expired", "persistence": "canonical_committed"}`。确认单 15 分钟时限从此是真实的生命周期而非摆设。

**② 墓碑项目写门禁（write-after-delete）**
六处补存活门禁（`lifecycle_state == "active"`）：`record_project_fact`、`start_project_task`、`sync_workspace` 项目查询、`checkpoint_project_task`、`finalize_project_task`、`project_of_task`（后四处在存在性查询中 join projects 过滤，store 层直接拦截，不再依赖 service 层）。删除项目后的迟到写入现在返回 `NOT_FOUND` 而非复活行。

**③ 通知真正送达（notify_review 空壳）**
- `inbox_only` 写真实 notifications 行：`trigger_type=review_item_pending`、`channel=inbox`、`dedupe_key=review_item:<item_id>`（幂等，重复投递去重）、`priority` 按 risk 映射（high/critical→high，否则 normal）、`reason` 带四种 item_type 的中文话术；插入后另排 `dispatch_notification` 派生作业。
- **迁移 `0013_review_notification_trigger`**：0011 的 CHECK 枚举不含新触发类型，收窄枚举让每条复核通知都 IntegrityError 死信——扩 `notification_trigger_allowed` 加入 `review_item_pending`。
- domain 触发器注册表 `_TRIGGERS`/`_NOTIFYING_TRIGGERS` 补录，白名单与现实一致。
- 四处 revision 登记表同步（e2e harness、全链 PG 测试、链完整性测试、备份源构建）。

**④ 文档**：`docs/zafiro-client-onboarding.md` 增"删除/复核（重要，这是设计不是 bug）"段落——`review.write@<内容域>` 授权模型、`review-access` 放行命令、通知盒机制、checkpoint/finalize 按任务所属项目授权。

**⑤ digest 全量处理**：删除 `MAX_SCOPES_PER_RUN = 5`，`selected = sorted(groups)` 处理全部作用域（原第 6 个起被静默截断）；每日 LLM 作业配额仍是预算兜底。

## 验证

- 新增 `tests/integration/test_governance_closures.py`（真实 PG harness）4 项：
  1. conflict 裁决闭合 conflicts 行且不再重新生成
  2. 过期删除计划终止为终态（item resolved + plan expired）而非永远 pending
  3. 墓碑项目拒绝全部六类写入/读取
  4. notify_review 写 notifications 行 + 幂等去重
- 全量回归：**584 passed / 12 skipped / 0 failed**（批 4 后基线 580 + 新增 4）。

## 生产验证（2026-09-25，实测通过）

| 验证项 | 方法 | 结果 |
|---|---|---|
| 迁移 0013 | `alembic_version` + `pg_get_constraintdef` | `0013_review_notification_trigger`；CHECK 枚举含 `review_item_pending` |
| 服务健康 | `GET /doctor`（192.168.10.7:18083） | `overall=healthy`，failed_jobs=0，findings 空 |
| 通知真正送达 | 手排 `notify_review` 作业指向 open 的 merge_candidate（39eecbb9），生产 worker 真实消费 | notifications 出现真实行：`review_item_pending / channel=inbox / state=delivered / priority=normal / risk=ordinary` |
| 通知幂等去重 | 第二次手排同 item 投递 | `notification_count=1`，重复作业 succeeded 不翻倍 |
| 墓碑写门禁 | MCP 真实链路：prod-trial 授权（project-access）→ rotate 刷新凭据 → `start_task` 已删除项目 | 返回 **NOT_FOUND**（store 层门禁拦截；修复前会成功创建任务行复活已删项目） |
| 死信 | jobs 状态分布 | succeeded 740 / cancelled 9 / **dead_letter 0** |

部署备注：secrets 必须指向 `/home/kms/personal-brain-v1-prod-data/secrets/`（与 db 容器挂载一致）——
`deploy/compose.prod.yaml` 头注释中的 `<secrets>` 是占位符；曾用旧目录 secrets 部署导致 migrate
密码认证失败。服务器上另有一套**旧版残留 stack**（`personal-brain-v1` 目录 + 本地 compose.yaml，
占 18081 端口，数据停在 2026-09-23），未动，处置建议见下。

## 遗留（批 6 后）

| 项 | 说明 | 建议 |
|---|---|---|
| 旧版残留 stack 未清理 | `/home/kms/personal-brain-v1`（老目录 + `deploy/compose.yaml`）的 api/worker/db/model-proxy 仍在运行，占 **18081**（zafiro 文档里写的端点）；其库数据停在 2026-09-23；有设备（192.168.10.4）持续 POST /mcp 到它并收到 401 | 与用户确认后 `docker compose -p personal-brain-v1 down`（保留卷），并把 zafiro 文档 §1 端点改为 18083 或隧道地址；两库卷独立，prod 卷是唯一真生产（raw_inputs 127 vs 13，写入到 9-24） |
| Bridge 离线队列未接线 | `PendingStore` 仍无入口引用（字段契约已对齐） | Bridge 启用时做 |
| digest 调度不补跨日 | 错过 03:10 窗口的当日摘要不会补算 | 数据量上来后再议 |
| nginx/隧道实机配置 | `client_max_body_size`、`proxy_read_timeout` 未核实 | 有网络层症状时查 |
