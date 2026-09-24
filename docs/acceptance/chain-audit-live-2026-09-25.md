# Chain-Audit 活体全系审查（2026-09-25，生产环境写入实测）

> 方法：`chain-audit` 技能（链路追踪 + 每环三问 + 断点清单）。与 2026-09-25 静态审查
> （`chain-audit-2026-09-25.md`，8 绳 34 项）不同，本轮在**生产环境**以真实 MCP 客户端
> 身份执行写入测试并监听服务端日志，把"链路通了"从静态推断升级为活体证据。
> 前置：Windows 本地 bridge 实例已全部关闭（3 组 personal_brain_bridge 进程），测试流量
> 全部指向 Linux 生产（192.168.10.7:18083）。日志留痕：`audit-2026-09-25/live-api.log`
> （169 行）、`live-worker.log`（28 行）。

## 一、入口盘点（本轮的绳子头）

| 绳子 | 入口 | 白话 |
|---|---|---|
| MCP 协议绳 | `POST /mcp`（remote.py:63） | 一切客户端流量的唯一大门 |
| 写入绳 | `tools/call` 写类工具（dispatcher:132） | 笔记/待办/账目/画像/项目五个内容域 |
| 治理绳 | `create_deletion_plan` → review_inbox_items | 删除/合并/矛盾的审批闭环 |
| 作业绳 | jobs 表 → worker 轮询 | 索引/刷新/通知的异步后半程 |
| 检索绳 | `search_brain` / `get_project_context` | 写入内容的可发现性 |

## 二、活体链路证据（每根绳子拉到底的结果）

**写入绳（5 域全通）**：`save_note`/`add_todo`/`add_expense`/`propose_self_claim`/`create_project`
全部 `accepted + canonical_committed`；库内落行（raw_inputs.content_text / todos / expenses /
self_claims(candidate,explicit,B) / projects）。claim 落库后 `index_self_claim succeeded`；
`extract_raw_input → index_raw_input → index_todo` 作业链全部 succeeded（jobs 表实证）。

**幂等链（批 4 修复活体确认）**：同 key 重放 → 静默返回首次结果；同 key 不同参数 →
`IDEMPOTENCY_CONFLICT`（带内 TOOL_ERROR）。生产首次实测。

**检索绳**：写入后 `search_brain` 在 knowledge（hybrid）/todo（exact）/finance（hybrid）均命中
写入内容；删除后同查询**卡片消失**——索引卡随墓碑退场，无"删了还搜得到"。

**项目绳**：`create_project → start_task → checkpoint_task → finalize_task → get_project_context`
全通；任务 state=completed；start/checkpoint/finalize 各触发一次 `refresh_project_context`
（succeeded ×3，jobs 实证）——change_event 索引由它承担。

**治理绳（批 6 主修的活体验证，真实业务流量触发，非手排作业）**：
```
create_deletion_plan（note/expense/claim/project 四类 target）
  → review_inbox_items(deletion_confirmation, open, risk=high, 15 分钟限时)
  → notify_review + dispatch_notification 作业 succeeded
  → notifications 行（review_item_pending / inbox / delivered
     "有一条删除申请等待你的批准（deletion_confirmation）"）
  → resolve_review_item approved（expected_version 栅栏）
  → 执行删除 → lifecycle_state=deleted（墓碑）
  → get_project_context → NOT_FOUND（读门禁）
```
四类 target 全部通过；全程 **dead_letter=0**；临时授予的 review.write@finance/self/projects
已用 `access=none` 全部回收。

**协议绳（批 1 修复活体确认）**：initialize → 会话头 → tools/call 全链 OK；丢会话（带版本头）
→ `MCP_SESSION_REQUIRED`；未知 JSON-RPC method → `-32004 NOT_FOUND`；工具内错误 → 带内
`isError=true + structuredContent.code`；越权 scope（diary）→ `SCOPE_DENIED`。

## 三、断点清单（本轮新发现）

| ID | 级别 | 白话 | 举例 | 证据 | 断点位置 |
|---|---|---|---|---|---|
| B1 | P3 | 未知工具名的错误码与 MCP 规范不一致 | 客户端调 `no_such_tool` 得到 `-32000 VALIDATION_FAILED`；MCP 2025-11-25 规范要求 `-32602 Invalid params`（"Unknown tool"）。严格 SDK 会把 -32602 当可恢复参数错误、-32000 当服务器错误，错误处理分支分叉 | 实测 `RPC_ERROR:-32000:VALIDATION_FAILED` | mcp_dispatcher.py:135-136 |
| B2 | 备忘 | 恢复视图的 checkpoint 只随活跃任务显示 | 任务 finalize 后 `get_project_context` 返回 `checkpoints:[]`——检查点数据仍在 checkpoints 表，只是恢复视图按活跃任务过滤（设计语义，建议写进 MCP_TOOLS 文档防误解） | 实测 active_task=null + checkpoints=[] | project_tools.py:126-133（内存版同语义） |
| B3 | 备忘 | 内部方法名与 MCP 工具名易混淆 | authorized_tools 有 `get_project_recovery`，MCP 面叫 `get_project_context`（映射同一实现）；直接调 `get_project_recovery` 得 `VALIDATION_FAILED`。MCP_TOOLS.md 记录的是 MCP 名（一致），调用方注意即可 | tools.py:25 | tools.py:25 |
| B4 | 运维 | `bash -s` 管道里 `docker compose exec -T` 会吞 stdin 剩余字节 | 清理脚本从 compose exec 那行起被整段吞掉、静默退出（字节级实证：远端完整收到 5422 字节，执行到 compose 行即停）。修复模式：所有 compose exec 加 `</dev/null` | 本轮 3 次脚本静默失败 | 运维脚本纪律，已入项目记忆 |
| B5 | 运维 | 服务器 sudo 时间戳按进程级隔离 + 授权命令 bump epoch | `sudo -v` 预热后 `sudo -n` 仍失败（缓存不共享）；project-access/review-access 后必须 rotate-client 刷新凭据（epoch 变更），否则 401 | 本轮多次实测 | 凭据流程纪律，已入项目记忆 |

## 四、分支账

- `notifications` 有两个生产者：notify_review（治理复核）与 brain_health_failure（体检），共用
  CHECK 枚举（0011+0013）；本轮只活测了前者，后者批 1 生产验证过。
- `merge_candidate 39eecbb9`（相似度 0.886 的画像重复）仍 open——**这是用户真实画像的裁决项，
  按铁律不替用户决定**，留待用户 `resolve_review_item`（approve=合并到 survivor，reject=保留两条）。
- conflict 型复核项的"批准后写回 conflicts"生产未活测（需在生产画像里制造矛盾 claim，污染
  数据）；集成测试 `test_governance_closures.py::test_conflict_verdict_closes_...` 已覆盖。

## 五、覆盖状态

**PASS（活体证据）**：协议绳、写入绳（5 域）、幂等链、检索绳（含删除后退场）、项目任务链、
治理绳（4 类 target + 通知 + 墓碑 + 读门禁）、作业绳（7 类作业 succeeded）、健康
（dead_letter=0 / doctor healthy）。

**PARTIAL（静态覆盖，未生产活测）**：conflict 写回（集成测试覆盖）、asset 上传（批 3 验证过）、
定时调度窗口（03:10-08:00 家族，明晨自动运行）、备份恢复（批 2 验证过）、Bridge 离线队列
（未接线，遗留）。

**与前轮审查的衔接**：chain-audit-2026-09-25.md 的 5×P1+10×P2 经批 1-4 修复；"值得修的 5 条"
（治理闭环/写门禁/通知/digest/文档）经批 6 修复——**本轮活体测试把其中可上生产的全部复验**。
仍未动的遗留：Bridge PendingStore 接线、digest 跨日补算、nginx 实机配置、旧版残留 stack
（18081 端口，待用户拍板）。

## 六、测试后状态

- 探针数据全部清理：笔记/账目/画像 claim 经治理链路删除（墓碑），todo 已完成，审查项目已
  删除（墓碑），临时 review 授权已回收（none）
- prod-trial 凭据已 rotate 到 epoch 35 并同步 secrets 文件（root 600），容器内 /tmp 中转副本
  已清除
- 服务全程 healthy，dead_letter=0，open_review_items=1（用户待裁决的 merge_candidate）
