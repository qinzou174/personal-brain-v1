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

Convergence status: **195/197 tasks complete**. The LAN deployment, owner/client
lifecycle, exact project grants, API/worker/bridge path, restart persistence and
isolated PostgreSQL regression are verified. T186 remains partially external:
TRAE CN is configured and its bridge path is behaviorally verified, but the
running IDE still needs a window reload for visible tool discovery; Cursor,
ChatGPT and real Trilium acceptance remain pending. Do not import real personal
data until an independent backup destination is approved and restored; see
`docs/USER_GUIDE.md` and `docs/acceptance/implementation-handoff.md`.
The Windows-local trial has passed real MCP save/search and isolated PostgreSQL
regression. T197 awaits a local Ark key file for chat/vector activation.
