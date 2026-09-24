# projects 通道修复验收证据（2026-09-25）

> 机检口径来自 `docs/tasks/handoff-20260925-项目通道收尾.md`（方案 B「一次修根」）。
> 环境：生产 `192.168.10.7:18083`（api/worker/db/model-proxy）+ 本机 uv venv +
> PostgreSQL 测试库 `brain_test@127.0.0.1:55432`。

## 一句话结论

projects 通道「只能建项目、其余全挂」的四个根因，加上通道修好后首次暴露的两个潜伏 bug
（事实刷新作业必死信、空名建项目产生空白索引死信），已全部修复、部署并复验；4 条历史死信
按证据注销（原因与交接描述不同，见 §3.2）；排序长度归一化经用户拍板一并提交部署并在生产
数据上确认生效（长档案「壁纸」由跌出前 30 变为第 2 名）。

## 1. 修复内容与提交

| 提交 | 内容 | 状态 |
|---|---|---|
| `dc88d70` | 通道主体：默认清单补 `project.read`（6 个读类工具不再 TOOL_DENIED）、建项目给创建者自授 `project:<id>` 作用域、`list_projects` 工具（32→33）、删除墓碑只写表里存在的列、验收测试 `test_projects_channel.py` | 已推送 + 已部署 + 当时真机 A1~A7 全绿 |
| `3c1063a` | OAuth 包装器委托 self-grant（修「直连生效、MCP 静默失效」） | 已推送 + 已部署 + MCP 复测通过 |
| `f2becf1` | ① 索引器新增 `_fact()`：支持 `decision:`/`constraint:`/`change_event:` 刷新作业（scope=`project:<id>`，双链 source_links）；② `create_project` 拒绝空 name/purpose → `VALIDATION_FAILED`；配套 2 个回归测试 | 本次推送 + 部署 + 生产复验通过 |
| `b4fbe10` | 排序长度归一化取代长度罚项：融合分不再乘长度（RRF 是唯一跨列排序权威），长度归一化留在词法列内部 `ts_rank_cd/(1+ln(len))`；`test_length_penalty.py` → `test_length_normalization.py` + 集成回归 `test_search_ranking.py` | 用户拍板后推送 + 部署 + 生产数据复验通过 |

本地聚焦回归（改动后）：

```
$env:BRAIN_TEST_POSTGRES_DSN="postgresql+psycopg://brain:<pwd>@127.0.0.1:55432/brain_test"
uv run pytest tests/unit/test_length_normalization.py tests/integration/test_search_ranking.py \
  tests/integration/test_projects_channel.py -q
→ 11 passed
```

（交接文档记录：含上述改动的本地全量 563 passed / 12 skipped。）

## 2. 验收矩阵（A1~A7）

| # | 场景 | 结果 | 证据来源 |
|---|---|---|---|
| A1 | `create_project` 建项目 | 通过 | 真机（上一会话）+ 本次生产 MCP 复验 |
| A2 | 建完立刻读回 `get_project_context`（self-grant 生效） | 通过 | 真机 + 本次复验 |
| A3 | `record_decision`/`record_constraint` 写入且上下文可见 | 通过 | 真机 + 本次复验（并新增：刷新作业 succeeded + 索引卡生成） |
| A4 | 任务全流程 `start_task`→`checkpoint_task`→`finalize_task` | 通过 | 真机（上一会话），本轮未重跑 |
| A5 | 项目内检索 `search_project` | 通过 | 真机（上一会话），本轮未重跑 |
| A6 | `list_projects` 可枚举（此前完全没有发现能力） | 通过 | 真机 + 本次复验（返回含 `lifecycle_state`，存活项目 0） |
| A7 | 治理删除：计划→批准→项目不可再读 | 通过 | 真机 + 本次复验（含事实依赖声明） |

## 3. 本轮（2026-09-25 深夜续作）执行证据

### 3.1 部署

`git pull --ff-only` → `3c1063a..b4fbe10`（7 文件）→ `docker compose -f deploy/compose.prod.yaml
up -d --build api worker`（四个 `BRAIN_*_FILE` 环境变量齐备）→ `migrate` 正常退出、
`db`/`model-proxy` healthy、api/worker 重启完成。

### 3.2 历史死信清理（4 条，原因与交接描述不同）

清理前逐条核查发现：交接文档称「作业引用的记录已删除」，实际**记录仍在**，但——

```
bootstrap_project        project:bb369236…  → projects.lifecycle_state = deleted（治理墓碑）
refresh_project_context  decision:a20e72e3… → decisions.lifecycle_state = active，所属项目
refresh_project_context  constraint:4a1603… → b244d92e（验收-项目通道）已 deleted
refresh_project_context  change_event:62cc… → 同上
```

即：所属项目已随治理删除，事实行未级联墓碑，**目标不再可索引**（若重跑会把已删项目的
事实重新写进检索面），因此注销结论正确、只是原因应记为「所属项目已治理删除」而非
「记录已删除」。执行：

```sql
update jobs set state='cancelled',
  error_summary='修复前产物：所属项目已治理删除，目标不再索引，运维注销（2026-09-25）',
  updated_at=now() where state='dead_letter';
→ UPDATE 4；remaining_dead=0
```

### 3.3 终验冒烟（MCP over LAN，凭据轮换制）

凭据：prod-trial 客户端 `8fd9fe36…` 轮换凭据到 `/tmp/trial.cred` 读出使用、用完即删
（**未轮换 zafiro `102b8f90…`**，避免手机端令牌失效；prod-trial 权限面与 zafiro 对齐，
仅补了本次冒烟所需、事后收回的 `review.write@projects`）。
脚本：`C:\Users\槐至\AppData\Local\Temp\prod_projects_smoke.py`（本地专用，未入库），
报告 `prod_projects_smoke_report.json`。19 项检查 → 16 OK、3 项经甄别非产品缺陷：

| 检查 | 结果 |
|---|---|
| `tools/list` = 33，含 `list_projects` | OK |
| `create_project` 空名 → `VALIDATION_FAILED`（-32000，JSON-RPC error 形态） | OK（脚本判定过严误报 FAIL，响应正确） |
| `create_project` → `71c8054f…` | OK |
| `get_project_context` 读回（self-grant） | OK |
| `record_decision`/`record_constraint` → 两条 `refresh_project_context:succeeded` | OK |
| 索引卡生成：`decision:…`/`constraint:…`，`scope=project:71c8054f…` | OK（**新修 `_fact()` 在生产首次生效**） |
| `list_projects` 含新项目 | OK |
| 删除计划 preview→批准→`execution_state=completed` | OK |
| 删除后 `list_projects`：项目转为 `lifecycle_state=deleted` 墓碑（冒烟当时仍列出；见 §4 B2，随后已改为只列存活） | 冒烟当时：设计如此（脚本按「消失」判定误报 FAIL）；现已修复 |
| 墓碑：`project=deleted`；`decision=active` | 见 §4 B1（真实的遗留缺口） |
| 删除 reconcile：`reconcile_deletion` 作业 succeeded，事实索引卡清零（cards_left=0） | OK |
| `dead_letter` = 0 | OK |

### 3.4 排序改动生产复验

对生产知识库（19 章节真实档案，全带向量）执行 `search_brain(query="壁纸")`：

- 命中 10 条，其中 7 条与壁纸相关；
- 链审时被旧罚项压出前 30 的 1663 字长档案（真实档案-英语/图像审美/角色卡/壁纸）
  现列 **第 2 名**（score 0.0308，仅次于专门的壁纸存档条目 0.0315）。

### 3.5 健康与清理后状态

```
GET /doctor → {"overall":"healthy","jobs":"healthy",…,"failed_jobs":0}
GET /ready  → {"ready":true,"database":"ok","worker":"ok","storage":"ok"}
clients: prod-trial epoch=7（已回收临时 project:<id> 与 review.write@projects，审计留痕）
         zafiro     epoch=8（未受影响，手机端令牌未动）
alive_projects=0；open_review_grants(prod-trial@projects)=0；dead_letter=0
```

冒烟自身残留：项目 `71c8054f…` 墓碑 1 行（治理删除的正常形态）+ 其两条事实行
（见 §4 B1，属同一遗留缺口）+ 删除计划/审计/reconcile 记录（治理留痕，应保留）。

## 4. 新发现与遗留

验收中发现的三个缺口，经用户拍板**当轮全部修复**（`f2becf1` 之后的补丁提交，见 §6）：

| 编号 | 发现 | 证据 | 处置 |
|---|---|---|---|
| B1 | **删除计划不级联墓碑项目事实**：`_execute_approved_deletion_plan` 的 `table_for` 映射缺 `decision`/`constraint`/`change_event`，声明为 dependents 也只会写删除动作+清索引，事实行永远停在 `active` | 本轮：`project=deleted, decision=active`（含交接前的 b244d92e 三事实） | **已修**：`table_for` 补三张事实表，声明为依赖的事实随项目一起墓碑；回归 `test_governed_deletion_cascades_to_facts_and_seals_reads` |
| B2 | `list_projects` 返回墓碑并带 `lifecycle_state`（客户端需自行过滤） | 本轮 7 条返回中 6 条为墓碑 | **已修（行为变更）**：服务端只列 `lifecycle_state='active'`，字段保留兼容 |
| B3 | `get_project_recovery` 不筛 `lifecycle_state`（已删项目仍可读回详情，连带 `get_active_task`/`get_recent_changes`/`check_freshness`/`get_module_context` 四个工具） | 交接文档已记录；本轮复现 | **已修**：读路径加 `lifecycle_state='active'`，墓碑项目一律 `NOT_FOUND` |
| B4 | ~~排序长度归一化是否提交部署~~ | 本轮已完成（§1、§3.4） | —— |
| B5 | 手机端「主动性」四层方案（提示词/看提醒工具/归档脚本）只给过文字，未实施 | 交接文档遗留② | 待用户排期 |
| B6 | 画像里可能仍有 open 的 `merge_candidate` 等用户在手机上批准 | 交接文档遗留③ | 用户手机侧处理 |
| B7 | 写入路径未随删除封口：`record_project_fact`/`start_project_task`/`sync_workspace` 仍可对墓碑项目写入（前提客户端仍持该项目作用域） | 代码静态核查（未在真实环境触发） | **部分收口**：检索侧已封死（索引器按父项目状态门禁，写入也生不出卡）；写入仍会落行，属待拍板的残留 |
| B8 | `NOT_FOUND` 在 MCP 层映射为 JSON-RPC `-32601`（"unknown method" 语义），已删项目读回时客户端可能误读为"工具不存在" | 本轮生产实测 `{"code": -32601, "message": "NOT_FOUND"}`（`remote.py` 注释称此为有意约定） | 观察项：若要更准确，可改映射为服务端错误段 `-32004` 之类并在 code 里保留字符串（需拍板） |
| B9 | `project-access --access none` 只摘掉客户端 scopes 并把 epoch+1，不像 `review-access` 那样把授权行 `effective_to` 收口 | 代码审阅（`admin.py` 两处实现不对称）；生产数据亦可见 zafiro 对已删项目仍留 open 授权行 | 观察项：统一为"撤销即收口"（低风险，可随下次改动带上） |

## 5. 复现方式速查

```
# 生产执行单行命令
uv run python deploy/windows-local/server_exec.py "<命令>"
# 生产只读/运维 SQL（stderr 的 cat: permission denied 是无害噪声）
uv run python deploy/windows-local/server_sql.py "<SQL>"
# 客户端凭据轮换（读→用→rm，避免长期落盘）
docker compose -f deploy/compose.prod.yaml exec -T api python -m personal_brain_server rotate-client \
  --client-id <client-id> --credential-file /tmp/trial.cred
# MCP 冒烟：C:\Users\槐至\AppData\Local\Temp\prod_projects_smoke.py <cred-file>
# 删除封口终验：prod_seal_probe.py <cred-file> <phase>；孤儿子项清卡：prod_child_cleanup.py
```

## 6. 用户拍板后的收尾补丁（2026-09-25 深夜续作第二轮）

§4 的 B1/B2/B3 当轮修完后，生产终验又逐层暴露出三个「修复的连带缺口」，均已修复、部署、并在生产复验：

| 提交 | 内容 | 触发证据 |
|---|---|---|
| `b1fd872` | 删除执行器 `table_for` 补 `decision`/`constraint`/`change_event`；`list_projects` 只列存活；`get_project_recovery` 加 `lifecycle_state='active'`（连带 4 个读类工具） | B1/B2/B3 |
| `19c1614` | ① 删除计划**服务端自动发现**项目的三个事实表（客户端不声明也会随项目删除，预览里可见）；② 索引作业在源已墓碑时结算为 `{"indexed": false, "skipped": "source_gone"}` 的成功作业，不再死信 | 生产实测：删项目后仍在队列的刷新作业 dead_letter（NOT_FOUND），会让 `/doctor` 变不健康 |
| `fa6ff94` | 事实表 `(owner_id, deduplication_key)` 唯一键与去重查询的 active 过滤不匹配：重复一条**已被删除**的语句会撞唯一键 → 未捕获 IntegrityError → HTTP 500。改为按生命周期分支：存活重复 → `duplicate` 回放；已删重复 → `{"status": "deleted", "persistence": "tombstone"}`（删除内容永不重建，与 `idempotency.py` 一致） | 生产实测：`record_decision` 复述已删语句 → 500（`uq_decisions_dedupe`） |
| `9142c55` | ① 删除计划自动发现项目下的 `project_tasks` 与 `checkpoints`（这两张表没有 `lifecycle_state`，只能靠删除动作清卡，此前 2 张验收残留卡片就是这么留下的）；② 索引器 `_project` 对项目、任务、检查点、工作区观测统一按**父项目存活**门禁，杜绝晚到作业给已删项目重建卡片 | 生产实测：上一会话验收项目 b244d92e 删除后，其任务/检查点 2 张卡仍可被持作用域的客户端检索到 |

生产终验（`prod_seal_probe.py final2`，MCP over LAN，**19/19 全绿**）：

```
cascade: project=deleted, decision=deleted          # 事实随项目墓碑
read sealed: get_project_context -> NOT_FOUND       # 读路径封死
discovery: list_projects -> []                      # 墓碑不再出现
cards_left=0 (project/decision/task/checkpoint)     # 四类卡全清
dedupe replay -> {"status":"deleted","persistence":"tombstone"}   # 不再 500
dead_letters=0                                      # 无新增死信
```

另：先前那条竞态死信（`4e6019a9`，`refresh_project_context | decision:fb34dca0…`）部署后**重排执行成功**，
结果 `{"indexed": false, "skipped": "source_gone", "target_ref": "decision:fb34dca0…"}` —— 同一作业由死信转为声明式跳过。

本地回归（最终代码）：`uv run pytest tests -q --ignore=tests/benchmark` → **566 passed / 12 skipped / 0 failed**。

收尾状态：`alive_projects=0`、`dead_letter=0`、`project 作用域索引卡=0`、`/doctor = healthy`；
prod-trial 临时补的 `review.write@projects` 与全部临时 `project:<id>` 作用域已回收（撤销审计留痕），
临时凭据 `/tmp/trial.cred` 已删；zafiro（手机端）epoch 未变、凭据未轮换，全程未受影响。
历史验收项目 b244d92e 的 2 张孤儿子项卡片已走治理删除计划（`18531018…`）清除。