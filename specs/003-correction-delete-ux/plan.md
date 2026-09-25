# Implementation Plan: 笔记更正/删除与 AI 消费体验完善

**Branch**: `003-correction-delete-ux` | **Date**: 2026-09-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-correction-delete-ux/spec.md`

## Summary

补齐"写进去就要能改能删"的能力闭环：新增笔记更正（supersede）、待办删除、账目更正三个写工具；检索增加内容时间范围过滤；所有产生检索卡的写入响应带索引状态提示；画像主张提交时实时提示极性冲突；意图路由词表扩充；同名项目提示；A 类主张语义对齐（入库即生效）；已裁决审核项的明确反馈；项目创建者自授权补齐治理删除权限。

## Technical Context

**Language/Version**: Python 3.12（uv 管理，SQLite 测试 / PostgreSQL 生产）

**Primary Dependencies**: FastAPI + uvicorn（HTTP/MCP）、SQLAlchemy 2、pgvector、httpx

**Storage**: PostgreSQL（生产，迁移 0001..0013）；SQLite（单测，方言差异经 `_db_id` 适配）

**Testing**: pytest（unit/contract/integration + e2e postgres harness）

**Target Platform**: Linux 服务器 docker compose（api/worker/migrate/model-proxy/db）

**Performance Goals**: 检索延迟不劣于既有 RRF 基线；时间过滤为索引行内过滤不额外查源表

**Constraints**: 不新增授权面种类；不变更既有工具的响应契约（仅增字段）；全部变更保留审计

**Scale/Scope**: 工具面 34 → 37（update_note / delete_todo / correct_expense）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 校验 | 结论 |
|---|---|---|
| II Canonical Truth | 更正=新条目+旧条目归档（原文保留可追溯），不覆盖 | PASS |
| III Structured First | 时间范围过滤为确定性过滤；路由词表提升结构化命中 | PASS |
| IV Least Privilege | 新工具复用对应域既有权限；项目自授权仅补创建者自身项目的 review.write | PASS |
| V Lifecycle Integrity | supersede=归档保留旧原文（lifecycle=deleted + 更正链接可追溯），非物理删除 | PASS |
| VI Behavioral Evidence | 每项 FR 配 Given/When/Then；红测先行 | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/003-correction-delete-ux/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/mcp-tools.md
└── tasks.md             # speckit-tasks 输出
```

### Source Code (repository root)

```text
packages/domain/personal_brain_domain/
├── records/expenses.py          # （已修复）validate_money
├── records/self_model.py        # 新增：主张极性判别 helper（O-04）
packages/infrastructure/personal_brain_infra/
├── persistence/authoritative_store.py  # update_note/delete_todo/correct_expense/list_review_items/propose 变更
├── search/repository.py         # search 增加 content_time 范围过滤
├── search/indexer.py            # 卡片元数据补 content_time
apps/server/personal_brain_server/
├── api/authorized_tools.py      # 新工具服务方法 + 建项目同名提示
├── protocols/tools.py           # 工具面 34→37
├── __main__.py                  # implemented 集合 + UUID 字段
packages/infrastructure/personal_brain_infra/security/authority.py  # grant_project_scope 补 review.write
packages/infrastructure/personal_brain_infra/models/gateway.py      # （不变）
packages/domain/.../retrieval/router.py  # 词表扩充
tests/contract/ tests/integration/       # 红测先行
```

**Structure Decision**: 沿用既有分层（domain → infra store → server service → protocols 注册），不新建模块层级。

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| （无） | | |

## Phase 0 Research（要点）

见 [research.md](research.md)：supersede 用"新条目+旧条目 tombstone（deleted）+检索卡同步移除"；待办删除走 lifecycle_state（生产 todos 已有该列且无 updated_at——沿用 B-05 列守卫教训）；账目更正="旧账 tombstone + 新账生效 + 关联可追溯"；时间过滤以卡片元数据 content_time 承载、rebuild-index 回填；实时冲突为轻量启发式提示（权威深扫仍在每日作业）。

## Phase 1 Design

见 [data-model.md](data-model.md)、[contracts/mcp-tools.md](contracts/mcp-tools.md)、[quickstart.md](quickstart.md)。
