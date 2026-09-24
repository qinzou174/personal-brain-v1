# 后端活化验收证据（Δ1-Δ4，2026-09-25）

> 机检口径来自 `docs/tasks/design-20260924-后端活化反思/01-思考路径.md` §六；
> 实施计划 `02-实施计划.md`；执行记录 `.execution/tasks/ACT-20260925-backend-activation/`。
> 环境：本机 uv venv + PostgreSQL（测试库 brain_test@127.0.0.1:55432；本机实例 18082）。

## 一句话结论

"后端没有活起来"的 6 条链路断裂已全部接电：调度器每日自动排产 6 类周期性作业、
`save_note` 触发真实 LLM 抽取并生成 B 类候选、候选按证据自动升级/过期、矛盾自动进
Inbox、每日 digest 可检索可溯源、失败作业产生主动通知——且全套回归 533 passed / 0 failed
（基线 503）。

## 1. 测试证据（可复现命令与计数）

命令（本机，带真实 PG DSN）：

```
$env:BRAIN_TEST_POSTGRES_DSN="postgresql+psycopg://brain:<pwd>@127.0.0.1:55432/brain_test"
uv run pytest tests -q --no-header --ignore=tests/benchmark
```

| 门 | 结果 | 证据 |
|---|---|---|
| 基线（改造前） | 503 passed / 12 skipped / 0 failed | 2026-09-25 改造前全量运行 |
| 全量回归（改造后） | **533 passed / 12 skipped / 0 failed**（+30 项新测试） | 同上命令，改造后运行 |
| Δ1 调度器 | `tests/integration/test_scheduler.py` 3 passed | 到期才入队 / 同日幂等（重复 tick 与第二 worker 均 0 新增）/ 跨天新桶 / 多 owner 覆盖 |
| Δ1 纯函数 | `tests/unit/test_activation_lexicon.py::test_schedule_due_and_bucket_helpers` | 本地日边界 |
| Δ2 抽取 | `tests/integration/test_worker_extraction.py` 6 passed | 无网关跳过 / 正常抽取落库 / 配额拦截 / 幂等重放 / 畸形输出可重试 / 走真实 poller 结算 succeeded |
| Δ2 纯函数 | `test_parse_extraction_output_*`、`test_day_window_*` | JSON 内嵌解析、中文类别别名、非法候选丢弃、本地日窗口 |
| Δ2 契约 | `test_authoritative_store.py`（jobs 8 = 6 单作业 + save_note 双作业）、`test_full_chain_postgresql.py`（index 作业使记录可检索） | 拆分后原测试意图保持 |
| Δ3 演化 | `tests/integration/test_memory_evolution.py` 7 passed | A 类激活 / ≥3 来源·≥14 天·≥2 上下文晋升 / 不足则不晋升 / 证据表晋升 / 矛盾阻断+进 Inbox（去重）/ 过期与 historical / 过期条目退出检索 |
| Δ4 主动 | `tests/integration/test_daily_digest.py` 5 passed | 按 scope 分组、逐条回指 / 空窗口跳过 / 无模型诚实跳过 / 调度链路端到端 / 健康失败通知与冷却合并 |
| 注册表契约 | `test_runtime_entrypoints.py`（含 4 个新作业类型） | 周期性作业类型都有归属 handler |
| 反退化 | 全套 0 failed；既有断言只做"契约变更后保持意图"的更新（`extract_raw_input`→`index_raw_input` 的索引归属、jobs 7→8 计数），无删除/弱化/跳过/加 mock | 见 `tests/` diff |

## 2. 真实运行证据（本机实例 18082，真实模型 + 真实数据库）

以新代码重启本机 API+worker 后，**无任何用户交互**，调度器自动排产并执行：

```
== jobs created in the last 2h ==   （deploy/windows-local/dbg_activation.py）
   conflict_scan succeeded 1
   daily_digest succeeded 1
   health_check succeeded 1
   promote_candidates succeeded 1
   retention_maintenance succeeded 1
   retention_sweep succeeded 1
== derived_contents ==
   digest active 1          # 生产首次出现 digest
   extracted_text active 7
== notifications ==          # 无失败作业 → 无通知（克制主动）
== dead_letter jobs == 0
```

digest 溯源机检（`deploy/windows-local/dbg_digest_trace.py`）：

- `derivation_version=digest-v1`，`confidence_inputs.model=deepseek-v4-1-flash`，
  `source_count=3`，窗口 2026-09-22T16:00Z–2026-09-23T16:00Z（本地 09-23 全日）；
- `summarized_from` 边 3 条；`search_index_entries` 命中 1 条（`target_type=derived_content`）；
- 载荷 JSON 中 `source_links` 3 条全部能在 `raw_inputs` 中找到（可回溯率 100%）；
- 摘要正文为记录内容的忠实要点（未编造）。

## 3. 反退化红线核对

| 红线 | 核对 |
|---|---|
| ① LLM 不参与金额/待办判定 | 抽取/摘要提示词显式排除金额·待办·日程；路由与存储未改动（`test_router_accuracy.py` 等 28+ 项回归通过） |
| ② 后台派生只进 derived + candidate | 抽取落 `derived_contents(canonicality='derived')` 与 `self_claims(policy_class='B', establishment='candidate')`；无 canonical 直写（`test_worker_extraction` 断言 raw 保持 canonical） |
| ③ 升级/降级/冲突留痕可回溯 | 晋升/激活/过期/历史都写 `correction_events`；冲突写 `conflicts` + Inbox 项（测试断言） |
| ④ digest/回答可溯源 | digest `source_links` 100% 覆盖来源，`summarized_from` 边逐条回指 |

## 4. 生产实例（192.168.10.7:18083）本轮部署后的实跑

部署：`git pull --ff-only`（a1614cc → 51f2662）→ `docker compose -f compose.prod.yaml up -d
--build api worker`（migrate 先行 Exited(0)、model-proxy healthy、api/worker 重建启动）。

无用户交互下，调度器首个 tick 即排产并全部成功（`server_sql.py` 只读查询）：

```
daily_digest | succeeded | 1 | 2026-09-24 10:16:14Z   （窗口=前一日本地日，当日库内无前日内容 → 诚实 skip）
promote_candidates | succeeded | 1
retention_sweep | succeeded | 1
conflict_scan | succeeded | 1
retention_maintenance | succeeded | 1
health_check | succeeded | 1
dispatch_notification | succeeded | 1
```

- **主动通知实测**：health_check 检出 2 个历史 dead_letter（parse_asset，旧瑕疵）→ 生成
  一条 notification 并经 dispatch_notification 送达：
  `brain_health_failure | inbox | high | delivered | failed_jobs=2 stale_modules=0`
  （这正是"系统异常要主动告诉主人"的设计行为；作业本身未做任何自动清理，人工决定）。
- **"克制"对照**：本机实例当日无失败作业 → notifications 表为空（不发无谓通知）。

## 5. 真实模型抽取实测（本机实例，`dbg_activation_extract.py`）

写入一条偏好类笔记（`save_note`，真实 AuthoritativeStore）后，运行中的 worker 自动完成：

```
jobs:    index_raw_input succeeded / extract_raw_input succeeded
derived: kind=description state=active payload_ref=<stored json>
claims:  preference  用户最近越来越喜欢手冲咖啡        B/candidate/candidate  api:knowledge
         habit       用户早上先来一杯拿铁已经成了习惯    B/candidate/candidate  api:knowledge
         interest    用户周末喜欢去山里徒步            B/candidate/candidate  api:knowledge
evidence rows: 3
```

即"记一条 → LLM 抽取 → B 类候选 + 证据行"的完整链路在活实例上用真实模型跑通；
候选不会直接成为事实（需 Δ3 的证据门槛）。

> 说明：`deploy/windows-local/dbg_activation*.py`、`server_sql.py` 为本机运维工具
> （本地未入库，与本仓库既有 dbg_* 脚本同类）。

## 6. 尚未覆盖 / 后续观察

- 生产库首份 digest 将于部署后第一个 03:10（本地）对"当日记录"生成（本轮窗口内无前日数据，属诚实跳过）；
- 候选升级（B→established）需 ≥14 天证据跨度，属"中间线"指标，需一周真实使用后回看；
- 冲突 Inbox 的自动触发依赖"同主题相反极性"的记录实际出现（测试已构造验证）。