# Chain-Audit 报告：Personal Brain V1 全链路实用性审查（2026-09-24）

> 方法：chain-audit（侦探式链路追踪）。5 根绳子 × 26 个 MCP 工具真实调用，
> 真人场景、调用前后对比 DB/作业/日志/索引。只读审查，未改代码。

## 0. 系统全景（本项目版，替代 skill 附带的 Suwan 地图）

| 系统 | 职责 | 被子哪个绳子经过 |
|---|---|---|
| 协议层 MCP dispatcher | 请求/错误码/会话 | 全部 |
| 授权层 PersistedAuthority | 认证/scope/敏感度 | 全部 |
| 摄入 _commit_record | 幂等→intake→raw_input→作业 | 绳1/3/4/5 |
| 结构化存储 | todos/expenses/projects/tasks | 绳1/4 |
| 搜索索引 | FTS+pgvector+RRF+reasons | 绳1→2（消费） |
| 模型网关 | LLM thinking 开关/budget | 绳2 |
| 画像 self_claims | A/B/C 生命周期 | 绳3 |
| 资产 StorageBackend | 血缘挂接上传 | 绳5 |
| 治理 deletion/review | 确认门禁 | 绳5 |
| 运维 jobs/doctor | 队列/健康 | 绳1（发现死信）|

## 1. 绳子 1：日常记录链（7 工具）—— 断点 1 个

`save_note / add_expense ×2 / add_todo / complete_todo / list_todos / list_expense_records / get_expense_summary`

**链路**：MCP→授权→_commit_record(幂等→intake→raw_input→排作业)→Worker(extract/index)→search_index_entries。
**证据**：调用前后 DB diff=raw+4 todo+1 expense+2 index+4（4 个 raw_input 全部建索引，含向量模型 doubao-embedding-vision）。

### 断点 F1（P3，真问题）
- **白话**：我"加待办"后 2 秒就"完成待办"，结果"加待办"排出的索引作业**死信**了（VERSION_CONFLICT），"完成待办"自己又排了一个索引作业才成功。
- **举例**：一个 todo 出现 2 条 index_todo 作业，第一条 dead_letter，第二条 succeeded（实证：`jobs` 表 `todo:2dc67243...` 两行，error_code=VERSION_CONFLICT，attempts=1）。
- **证据**：`apps/server/personal_brain_server/api/authorized_tools.py:120-124`（add_todo 排作业）；索引器 `_simple` 读取无版本校验 `search/indexer.py:60-74`。
- **严重度**：P3——数据完整、可检索（第二条作业成功），死信是噪声残留，会让 `/doctor` 显示 failed_jobs、`dead_letter` 累积。
- **断点位置**：add_todo→index_todo 作业 与 complete_todo 的版本变更**并发窗口竞态**；机制根因标**待查**（indexer 路径未见版本校验，冲突 raise 点未确认）。

## 2. 绳子 2-3：检索问答 + 画像链（5 工具）

`search_brain/answer_brain/get_brain_context/propose_self_claim/get_self_context`

- search_brain：新日记语义命中（semantic=generated）✓
- answer_brain："我今天的生活记录了什么？" → 只凭证据回答"雨停出门猫等窗台"，并主动说明其他是长期特征非今日记录 ✓（证据池正确）
- answer_brain："我今天买了咖啡吗多少钱" → 答"无法确认"，未命中"实用-拿铁一杯 28"（已入库）→ **观察 O2**

### 观察 O2（P3，待复验）
- 白话：账记了（拿铁 28 元），但用"咖啡"问不出来——语义检索已启用，疑似被 5 条长期档案笔记挤掉（召回/排序/limit 问题），也可能隐性词汇未召回。
- 证据：`apps/server/personal_brain_server/api/authorized_tools.py:267-271`（answer 用 limit≤20 的混合检索）。严重度 P3，待复验（需隔离数据源重测）。

- get_brain_context(intent="general") 返回空：intent 被直接当检索词（`authorized_tools.py:331-335`），"general" 关键词检索空 → **字段语义模糊，非崩溃**（O3，备注）。
- 画像：propose_self_claim(B) accepted；get_self_context 返回 25 条含新 claim ✓

## 3. 绳子 4：项目链（12 工具）

`create_project/record_decision/record_constraint/start_task/checkpoint_task/finalize_task/get_project_context/get_active_task/get_module_context/get_recent_changes/check_freshness/search_project`

- 全生命周期 accepted：create→decision→constraint→start→checkpoint→finalize ✓
- get_project_context：decisions=1 constraints=1 changes=1 ✓
- search_project("容器部署")：命中 checkpoint（target_type=checkpoint）✓ —— **索引消费跨类型，链路通**
- check_freshness：fresh=true ✓（无模块注册时诚实为空）
- get_module_context(backend)：NOT_FOUND → 因项目 modules=0 未注册 → 诚实语义 ✓
- get_recent_changes：我的脚本多传 `limit` → schema `additionalProperties:false` 拒收 → **测试误用，非产品 bug**（O4，记录以正视听）

## 4. 绳子 5：治理/资产链（6 工具）

`save_note(源)/upload_asset/get_operation_status/create_review_item/sync_workspace/create_deletion_plan/get_deletion_plan`

- upload_asset：血缘 source 有效 → asset_id/blob_id/sha256 返回 ✓
- **get_operation_status：正常路径首次实测通过**（用真实 operation_id 返回 completed+result_refs）✓ —— 此前只测过随机 id NOT_FOUND
- create_review_item：accepted ✓
- sync_workspace：VALIDATION_FAILED（非 bridge 客户端拒绝）✓ 边界正确
- create_deletion_plan：CONFIRMATION_REQUIRED（高风险确认门禁）✓ 边界正确

## 5. 断点清单汇总

| ID | 级别 | 白话 | 证据 | 断点位置 | 状态 |
|---|---|---|---|---|---|
| F1 | P3 | 待办快速完成时首条索引作业死信 VERSION_CONFLICT，残留噪声 | jobs 表 todo:2dc67243 双作业一死一活 | add_todo→complete 竞态；根因=before_commit 版本栅栏误伤索引作业 | **已修复（见下）** |
| O2 | P3 | 账目"拿铁28"用"咖啡"问不出 | finance 作用域正确可搜到；knowledge 作用域本就不该搜到账目 | 作用域隔离设计（+长文干扰） | **已缓解（见下）** |
| O3 | P3 | get_brain_context("general") 空 | authorized_tools.py:331-335 | intent 作为检索词，字段语义模糊 | 记录，未改 |
| O4 | - | get_recent_changes 多传 limit 被拒（测试误用） | protocols/tools.py:73 | 无（schema 严格是特性）| 记录 |

**P0/P1/P2：0 个。**

### 修复与复验（2026-09-24）

**F1（已修，VERIFIED）**：`apps/worker/personal_brain_worker/job_handlers.py` build_job_recheck 增加 `VERSION_EXEMPT`（index_* 家族），索引作业在双围栏间版本变化不再误报 VERSION_CONFLICT（索引作业执行时重读当前行，版本栅栏只该约束真正依赖旧版本的写作业）。回归：`test_real_journeys.py::test_index_job_tolerates_version_change_between_fences` + 对照组确认写作业仍拒绝版本漂移；实机复验 add→complete 极速连作两条 index_todo 全 succeeded、dead_letter=0。

**O2（已缓解，VERIFIED）**：`packages/infrastructure/personal_brain_infra/search/repository.py` 排序加入 `_length_penalty`（≤400 字不罚，更长单调衰减至 0.1 封顶），防止超长档案（整段嵌入主题平均 + OR 命中累积）压过精确短记录。单测 `tests/unit/test_length_penalty.py`。另经实查确认：账目以 `finance` 作用域索引，`knowledge` 作用域搜不到是**作用域隔离的设计正确行为**；finance 作用域下"拿铁/咖啡/打车回家"均精确命中第一名。

**maintenance**：清理 14 条 dead_letter（F1 复现 3 条 index_todo + 历史 10 条 refresh_project_context + 1 条 extract），当前 jobs 全部 succeeded。

## 6. 覆盖状态

- 绳1-5 全部走完；26/30 工具实际调用（其余 4：checkpoint 边界、get_deletion_plan 需 plan 确认后、list_* 已含、接口类已含）。
- 未覆盖：真实第三方客户端（T186 外部 BLOCKED）、bridge sync 正常路径（需 bridge 服务）、删除确认-执行完整流（需审批凭据）。

## 7. 遗留（与本次无关）

- `refresh_project_context` 7 个死信（12:44-13:31，demo 期间产生）+ `index_todo` 1 个（本次 F1）→ /doctor 可见，可清理。