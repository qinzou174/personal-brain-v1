# Project Brain durability evidence — 2026-09-23

Status: **PASS** for T178's local implementation and automated acceptance scope.

## Implemented behavior

- Bootstrap discovery walks only the explicitly approved repository root, discovers real top-level modules, hashes bounded source files and excludes dependency trees, environments, caches, build output, archives, databases, logs, model binaries and credential-like files.
- Git observation uses the actual repository revision, branch and porcelain working-tree state with command timeouts and hard path/hash limits. It rejects a parent repository when the approved root is only a subdirectory.
- Incremental mapping treats a changed descendant as affecting its owning module rather than requiring an exact filename match.
- Workspace observations, refreshed or stale module cards, current project revision evidence, an intake record, body-free audit event, durable refresh job and idempotency outcome commit in one UnitOfWork.
- Once a project is bound to an approved root identity, a later sync from a different root fails with `WORKSPACE_BOUNDARY_VIOLATION`.
- Start/checkpoint/finalize state retains revisions, dirty/change evidence, affected modules, constraints, decisions, verification and remaining work. Decisions, constraints and final change events are canonical persisted records.
- A newly constructed store with no process history recovers project profile, active task, checkpoints, modules and freshness warnings, decisions, constraints, recent changes and the latest workspace evidence.

## Verification

- Focused bridge, workspace-boundary, project persistence and runtime tests: **24 passed**.
- Full repository regression after implementation: **374 passed, 13 skipped**.
- Skips are declared environment/external-client gates; no test failure was suppressed.
- The PostgreSQL 0001..0011 physical schema and rollback were independently proven in `migration-postgresql-2026-09-23.md`; the persistence tests use a restartable on-disk database to prove process-independent recovery behavior.

## Honest boundary

This evidence proves the implementation and automated local behavior. It does not claim the externally gated TRAE, Cursor, ChatGPT or Trilium acceptance in T186.
