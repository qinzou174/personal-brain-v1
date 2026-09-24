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
| 删除后 `list_projects`：项目转为 `lifecycle_state=deleted` 墓碑（**按设计仍列出**） | 设计如此，脚本按「消失」判定误报 FAIL |
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

## 4. 新发现与遗留（待拍板）

| 编号 | 发现 | 证据 | 建议 |
|---|---|---|---|
| B1 | **删除计划不级联墓碑项目事实**：`_execute_approved_deletion_plan` 的 `table_for` 映射缺 `decision`/`constraint`/`change_event`，声明为 dependents 也只会写删除动作+清索引，事实行永远停在 `active` | 本轮：`project=deleted, decision=active`（含交接前的 b244d92e 三事实） | 小改：给 `table_for` 补三张事实表（`decisions`/`constraints`/`change_events`），补回归测试 |
| B2 | `list_projects` 按设计返回墓碑并带 `lifecycle_state`（客户端需自行按 `lifecycle_state != 'deleted'` 过滤） | 本轮 7 条返回中 6 条为墓碑 | 若希望手机端「删了就消失」，可在服务端加存活过滤（行为变更，需拍板） |
| B3 | `get_project_recovery` 不筛 `lifecycle_state`（已删项目仍可读回详情，前提是客户端仍持有该项目作用域） | 交接文档已记录；本轮未复测 | 补 `lifecycle_state='active'` 过滤 |
| B4 | ~~排序长度归一化是否提交部署~~ | 本轮已完成（§1、§3.4） | —— |
| B5 | 手机端「主动性」四层方案（提示词/看提醒工具/归档脚本）只给过文字，未实施 | 交接文档遗留② | 待用户排期 |
| B6 | 画像里可能仍有 open 的 `merge_candidate` 等用户在手机上批准 | 交接文档遗留③ | 用户手机侧处理 |

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
```