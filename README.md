# Personal Brain V1

Private, evidence-grounded, single-owner personal Brain: one canonical store,
raw-first capture, exact structured records, project continuity, bounded
retrieval and governed lifecycle.

## Layout

- `packages/domain/personal_brain_domain` - domain invariants
- `packages/infrastructure/personal_brain_infra` - persistence/storage/search/jobs
- `apps/server/personal_brain_server` - API/protocol adapters
- `apps/worker/personal_brain_worker` - durable background jobs
- `apps/bridge/personal_brain_bridge` - workspace-bounded local bridge
- `migrations` - Alembic chain 0001..0011
- `specs/001-personal-brain-v1` - spec/plan/tasks/contracts
- `docs` - operator and client documentation

## Quickstart (suites)

See `specs/001-personal-brain-v1/quickstart.md`. Command contract:
`pytest tests/unit|contract|integration|security|migration|acceptance|restore`.

For the actual user workflow and current activation blockers, see
[`docs/USER_GUIDE.md`](docs/USER_GUIDE.md).
Windows 本机试用入口见 [`docs/WINDOWS_LOCAL_TRIAL.md`](docs/WINDOWS_LOCAL_TRIAL.md)。

## Status

Convergence status: **195/197 tasks complete** plus feature `002-mcp-fixes`
(**27/27**): ranking_reasons 接线（ER-03 可解释排序）、Trilium 可选部署
（compose profile extras，默认关闭不影响核心）、本机真实模型激活
（T197，`answer_brain` 真实接地 + 向量命中，见
`docs/acceptance/t197-local-model-2026-09-24.md`）。Full suite now
**447 passed / 23 skipped / 0 failed**. T186 remains partially external:
TRAE CN is configured and its bridge path is behaviorally verified, but the
running IDE still needs a window reload for visible tool discovery; Cursor,
ChatGPT and real Trilium acceptance remain pending. Do not import real personal
data until an independent backup destination is approved and restored; see
`docs/USER_GUIDE.md` and `docs/acceptance/implementation-handoff.md`.
The Windows-local trial has passed real MCP save/search, isolated PostgreSQL
regression and real model grounding.
