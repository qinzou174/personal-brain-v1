# Implementation Plan: MCP 修复与模型激活

**Branch**: `002-mcp-fixes` | **Date**: 2026-09-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-mcp-fixes/spec.md`

## Summary

本特征把反思报告的三个收敛动作固化到 002：
1. **Δ1 ranking_reasons 接线**：让检索排序的理由真正从 ranking 管线输出（compiler 消费 RankedHit.reasons），并在 `search_brain` / context package 返回 `ranking_reasons` 字段，向后兼容。
2. **Δ2 Trilium 可选部署**：`deploy/compose.yaml` 增加 `profiles: ["extras"]` 的可选 trilium 服务，默认不开、关掉不影响核心。
3. **T197 本机模型激活**：放置 Ark Key 至 `E:\Personal-Brain-V1-local\secrets\model-api-key`，重启本机实例后验证真实 `answer_brain` 与向量检索（对话 deepseek-v4.1-flash / 向量 doubao-embedding-vision）。

## Technical Context

**Language/Version**: Python 3.11+（既有 monorepo，uv 管理）
**Primary Dependencies**: 既有 personal_brain_domain / personal_brain_infra / personal_brain_server；Compose（Docker）；无新增第三方依赖
**Storage**: PostgreSQL/pgvector（本机与局域网各一实例）
**Testing**: pytest（既有 30+ 套件），新增局部单测 + 契约测试
**Target Platform**: Windows（本机）/ Linux+Docker（局域网）
**Project Type**: 服务端 monorepo（server/worker/bridge + domain/infra）
**Performance Goals**: 无新预算要求；保持 ER-12 基准不回退
**Constraints**: 密钥零入库/日志/文档；431 passed 零回归；compose 向后兼容；本机与局域网独立
**Scale/Scope**: 单用户；改动面 3 个（检索管线、compose、本机运行时）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 判定 |
|---|---|
| II. Canonical Truth, Provenance, Honest Uncertainty | PASS — ranking_reasons 让"为什么这样排"可解释，强化诚实的排序来源 |
| III. Structured Before Probabilistic | PASS — 不动结构化路由；仅让排序可解释 |
| IV. Privacy & Secret Exclusion | PASS — 密钥仅本地文件，不进 git/日志/文档 |
| VII. V1 Scope Discipline | PASS — Trilium 为"可移除客户端"，profiles 默认关闭；模型激活为既有 T197 闭环 |
| VI. Behavioral Evidence | PASS — 每项有 GWT 验收与回归口径 |

无违规，无需 Complexity Tracking。

## Project Structure

### Documentation (this feature)

```text
specs/002-mcp-fixes/
├── plan.md              # 本文件
├── research.md          # 决策记录
├── data-model.md        # 排序理由字段与兼容契约
├── quickstart.md        # 端到端验证指南
├── contracts/
│   └── ranking-reasons.md  # ranking_reasons 字段契约
└── tasks.md             # $speckit-tasks 输出（下阶段）
```

### Source Code (repository root)

```text
# Δ1 检索排序理由接线
packages/domain/personal_brain_domain/retrieval/
├── ranking.py            # 扩展: reasons 采集 freshness/confidence/source_trust
└── compiler.py           # 修改: 消费 rank_hits 输出，携带 reasons 进 ContextPackage
packages/infrastructure/personal_brain_infra/search/    # 只读不改
apps/server/personal_brain_server/
├── api/context_tools.py       # 修改: search_brain 序列化 ranking_reasons
└── protocols/tools.py         # 扩展: schema 增加可选 ranking_reasons 输出说明（可选）
tests/
├── unit/test_ranking_reasons.py      # 新增
└── contract/test_ranking_contract.py # 新增

# Δ2 Trilium 可选部署
deploy/compose.yaml                # 修改: trilium 服务 + profiles: [extras]
deploy/trilium-compose.example.yml # 新增: 独立参考文件

# T197 本机模型激活（运行时数据，非代码）
E:\Personal-Brain-V1-local\secrets\model-api-key        # 运行时密钥文件（不入库）
docs/acceptance/t197-local-model-2026-09-24.md          # 证据（密钥值绝不写入）
docs/WINDOWS_LOCAL_TRIAL.md                             # 更新: 模型激活说明
```

**Structure Decision**: 沿用既有 monorepo 布局；改动仅限上述文件，不新增包/模块边界。

## Complexity Tracking

> 无宪章违规项，此表留空。