# Tasks: MCP 修复与模型激活

**Input**: Design documents from `/specs/002-mcp-fixes/`

**Prerequisites**: plan.md、research.md、data-model.md、contracts/ranking-reasons.md、quickstart.md

**Tests**: 本特征采用 TDD：每个用户故事先写失败测试 → 实现 → 回归 → 证据。

**Organization**: 按用户故事分组；每个故事可独立实现与验收。

## 格式说明

- **[P]**: 可并行（不同文件、无依赖）
- **[Story]**: US1=ranking_reasons 接线，US2=Trilium 可选部署，US3=本机模型激活（T197）
- 复用既有任务标识：Δ1↔ER-03/FR-057，Δ2↔FR-100/US12，T197↔T197

---

## Phase 1: Setup（共享基础）

**Purpose**: 特征目录与测试占位初始化（复用既有仓库结构，无需新脚手架）

- [X] T001 确认特征目录产物齐备（plan/research/data-model/contracts/quickstart），无 NEEDS CLARIFICATION 残留
- [X] T002 [P] 记录特征基线：本机当前 `uv run pytest -q` 结果（≥431 passed / 0 failed）写入 `docs/acceptance/t197-local-model-2026-09-24.md` 前段

---

## Phase 2: Foundational（US 公共阻断）

**Purpose**: 检索命中信号采集的公共契约，US1 依赖；US2/US3 无代码公共项

**⚠️ 无 US 可在该阶段未完成时进入 US1**

- [X] T003 在 `contracts/ranking-reasons.md` 冻结 ranking_reasons 字段契约（array<string>，可空，顺序=命中顺序，信号字典：fresh/stale/confidence/source/single/rrf）——已在 plan 阶段完成，核对签名
- [X] T004 文档化 reasons 信号采集规则（freshness/confidence/source_trust→reasons 的映射）落 `specs/002-mcp-fixes/data-model.md`——已有，核对一致性

**Checkpoint**: 契约冻结，US1 可开工。

---

## Phase 3: User Story 1 - 检索结果可解释（Ranking Reasons）(Priority: P1) 🎯 MVP

**Goal**: `search_brain`/context package 返回每个命中的排序理由

**Independent Test**: 检索多命中/单命中/空命中，断言 `ranking_reasons` 字段随结果返回且与输入信号一致，旧消费无劣化

### Tests for US1（先写后实现，确保 FAIL）

- [X] T005 单元测试：混合候选（fresh+stale、高/低置信、不同来源）通过 `rank_hits` 后，`RankedHit.reasons` 包含对应信号（fresh/confidence/source），落 `tests/unit/test_ranking_reasons.py` [ER-03, FR-057]
- [X] T006 单元测试：单命中返回 `("single",)`、空/全被硬过滤返回空列表且不抛异常，落 `tests/unit/test_ranking_reasons.py` [FR-003]
- [X] T007 契约测试：`search_brain`（本机 MCP 直连）返回 `ranking_reasons` 字段（多命中为列表、单命中 `["single"]`、空 `[]`），旧 payload 结构兼容，落 `tests/contract/test_ranking_contract.py` [SC-001]

### Implementation for US1

- [X] T008 扩展 `packages/domain/personal_brain_domain/retrieval/ranking.py`：`rank_hits` 从 candidates 采集 freshness/confidence/source_trust/information_class 生成 reasons 元组（无信号时保持 `("rrf",)`/`("single",)`）[ER-03, FR-001]
- [X] T009 修改 `packages/domain/personal_brain_domain/retrieval/compiler.py`：指令消费 `rank_hits` 输出（替换现第 26 行"仅按 freshness 排序"的逻辑），将 `RankedHit.reasons` 携带进 Context Package 结果 [FR-001, FR-002]
- [X] T010 修改 `apps/server/personal_brain_server/api/context_tools.py`：`search_brain` 序列化时把 reasons 写入 `ranking_reasons` 字段（向后兼容，空/单结果不抛异常）[FR-002, FR-003]
- [X] T011 兼容校验：旧消费方缺失该字段不劣化；`additionalProperties: false` 的 inputSchema 不受影响（新字段只进 structuredContent 内层）[FR-002]

**Checkpoint**: US1 独立可测——运行 T005/T006 单测 + T007 契约测试 + `search_brain` 手动抽查全绿。

---

## Phase 4: User Story 2 - Trilium 可选部署（Δ2）(Priority: P2)

**Goal**: `deploy/compose.yaml` 提供可选 trilium 服务，默认关闭，不阻塞核心

**Independent Test**: `compose ps` 默认无 trilium；`--profile extras` 时出现且健康；关闭时核心零错误

### Tests for US2

- [X] T012 [US2] 部署边界测试：解析 `deploy/compose.yaml`，断言核心服务（api/worker/db）依赖树不含 trilium，且 `trilium` 段带 `profiles: ["extras"]`，落 `tests/contract/test_deployment_boundary.py`（既有文件扩展）[FR-004, FR-005]
- [X] T013 [US2] 契约测试：`profiles` 值只含 `extras`，默认 profile 不创建 trilium 容器（用 compose config 输出校验），落 `tests/contract/test_deployment_boundary.py` [SC-003]

### Implementation for US2

- [X] T014 [P] [US2] 修改 `deploy/compose.yaml`：新增 `trilium` 服务段（镜像 zadam/trilium:latest，volume 挂 trilium-data，`profiles: ["extras"]`，restart 策略与健康检查），不触碰 api/worker/db 段 [FR-004, FR-005]
- [X] T015 [P] [US2] 新增 `deploy/trilium-compose.example.yml` 独立参考（含启用方式注释，供需要者使用）[FR-005]
- [X] T016 [US2] 更新 `docs/TRILIUM_SETUP.md`：记录 compose 启用方式（`docker compose --profile extras up -d trilium`）与"默认关闭不影响核心"说明 [SC-003]

**Checkpoint**: US2 独立可测——T012/T013 全绿；局域网或本地 Docker 上 `--profile extras`/默认两态验证通过。

---

## Phase 5: User Story 3 - 本机模型激活（T197）(Priority: P1)

**Goal**: 本机实例真实对话 + 向量模型启用

**Independent Test**: `/ready` 显示模型启用；`answer_brain` 真实回答；向量检索命中非空；密钥缺失保持 fail-closed

### Tests for US3

- [X] T017 [US3] 单元测试：披载模型密钥文件存在/缺失两种设置场景，断言 `external_models_enabled` 正确翻转为 true/false 且缺失时仍 fail-closed（不报 500），落 `tests/unit/test_model_settings.py` [FR-006, FR-007]
- [X] T018 [US3] 密钥核验脚本：`git grep -n "<ark-key-prefix>" $(git rev-list --all)` 与 `Select-String -Path E:\Personal-Brain-V1-local\*.log` 均零命中，落 `docs/acceptance/t197-local-model-2026-09-24.md` [SC-005]

### Implementation for US3（多为运行时数据/验证，代码仅确认读取逻辑）

- [X] T019 [US3] 确认 `start.ps1` 密钥检测逻辑存在（`BRAIN_MODEL_API_KEY_FILE` 指向 `E:\Personal-Brain-V1-local\secrets\model-api-key`），缺失不改；必要时补齐检测行 [FR-006]
- [X] T020 [US3] 创建密钥文件：`E:\Personal-Brain-V1-local\secrets\model-api-key`（内容为 Ark API Key，仅本机运行目录，**绝不写入任何 git/日志/文档**；权限避免他人可读）[FR-007, SC-005]
- [X] T021 [US3] 重启本机实例（stop.ps1 → start.ps1），核对 `/ready` 中 `external_models_enabled=true` 且 models 项显示 [FR-006, SC-004]
- [X] T022 [US3] 真实验证：`answer_brain("本机模型激活验证", requested_scope="knowledge")` 返回真实生成回答；`search_brain` 带 `query_embedding` 与 `vector_model_version="doubao-embedding-vision"` 命中非空 [SC-004]
- [X] T023 [US3] 记录权威证据：`docs/acceptance/t197-local-model-2026-09-24.md`（含 ready 输出、answer 片断、命中数、密钥核验零命中；**不含密钥值**）；更新 `docs/WINDOWS_LOCAL_TRIAL.md` 模型激活说明 [SC-004, SC-005]

**Checkpoint**: US3 独立可测——T017 单测、T018 密钥核验、T020-T023 实机验证全绿。

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 回归、文档收口（本机与局域网独立，不改局域网）

- [X] T024 全量回归：`uv run pytest -q` ≥431 passed / 0 failed（新增测试计入），记录于 t197 证据文档 [SC-002]
- [X] T025 [P] 更新 `docs/acceptance/traceability-matrix.md`：登记本特征 FR(001-008)/SC(001-005) 到 ER-03/FR-057/FR-100/T197 的映射（追加一页，不动既有行）[SC-002]
- [X] T026 [P] 更新 `README.md` Status：本机模型已激活（T197 完成）、ranking_reasons 已接线、Trilium 可选部署 [SC-003]
- [X] T027 密钥安全终检：全历史 `git grep` 密钥前缀零命中 + 日志零命中，结论写入证据文档 [SC-005]

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无前置
- **Foundational (Phase 2)**: 依赖 Setup；INSEMINUS 全部并行（仅契约核对）
- **US1 (Phase 3)**: 依赖 P1+P2；无跨故事依赖
- **US2 (Phase 4)**: 依赖 P1；独立
- **US3 (Phase 5)**: 依赖 P1；独立（T019 仅确认无代码改动或更小）
- **Polish (Phase 6)**: 依赖 US1/US2/US3 完成

### 用户故事执行顺序

US1（P1）→ US2（P2）/US3（P1 可并行）→ Polish。US3 的密钥放置与实机验证可与 US1/US2 并行。
推荐 MVP = US1（20 分钟级代码改动 + 单测/契约测试）+ US3（密钥/重启/验证）。

### Within Each User Story

测试先写并 FAIL → 实现 → 回归 → 证据。

### Parallel Opportunities

- T002/T005/T006/T007 可并行（不同文件）
- T014/T015 可并行
- T019/T020 可并行（同密钥域，T020 是数据放置）
- US1/US2/US3 彼此独立，可并行

---

## Implementation Strategy

### MVP First（先 US1 + US3）

1. P1 Setup → P2 契约核对（快）
2. US1：T005-T011（ranking_reasons 全链）
3. US3：T017-T023（密钥+验证）
4. STOP & VALIDATE：quickstart.md 全部验证脚本
5. 再补 US2（compose profile）与 Polish

### Incremental Delivery

US1（MVP）→ US3（模型激活，价值大）→ US2（部署可选性）→ Polish 收口。每步独立可测、独立证据。

---

## Notes

- [P] = 不同文件、无依赖
- [Story] 映射 spec 用户故事；任务复用既有标识只读引用于任务描述（不重复定义既有 FR/T）
- 密钥纪律：所有实现与证据中**严禁出现完整 Ark Key 值**；核验只比对前缀
- 本机（127.0.0.1:18082）与局域网（192.168.10.7:18081）为独立数据域；本特征仅本机激活与验证，局域网仅同步代码（若改 compose/retrieval 需同步 + 重新部署验证）
- 提交策略：每个里程碑（US1 全绿 / US3 全绿 / US2 全绿 / Polish）后建立一次 commit（用户未要求时不自动提交）