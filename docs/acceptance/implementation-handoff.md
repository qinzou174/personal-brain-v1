# Implementation handoff

> **SUPERSEDED — 本文件已过期。** 任务数与测试数均停留在 2026-09-23。
> 接续工作请以 `docs/acceptance/stage-history-2026-09-24.md` 为准
> （当前 195/197 已勾选，本机 431 passed / 23 skipped / 0 failed，迁移 head 0012）。
> 本文件保留为 2026-09-23 阶段的历史记录。

Updated: 2026-09-23 (Asia/Shanghai)

## Task marker

**191/192 complete; 1 open.** `specs/001-personal-brain-v1/tasks.md` is
authoritative. T186 remains intentionally unchecked as
`EXTERNAL_VERIFICATION_PENDING` — live TRAE/Cursor/ChatGPT/Trilium accounts
and a reachable authenticated HTTPS/OAuth route are required and mocks never
substitute. TRAE CN is configured and the exact bridge path is behaviorally
verified, but visible IDE discovery still needs a window reload. Authoritative
post-deployment local run: **412 passed, 23 skipped, 0 failed**; isolated
PostgreSQL/pgvector run: **423 passed, 12 skipped, 0 failed**.

Phase 16 completed T171-T185 and T187. Phase 17 completed T188-T192. Open: T186
only. Evidence documents:
`mcp-full-surface`, `project-brain-durability`, `postgres-search`,
`offline-worker-durability`, `governed-deletion`, `oauth-provider-hardening`,
`real-journeys-2026-09-23`, `er12-benchmark-2026-09-23`,
`encrypted-backup-set-2026-09-23`, `migration-postgresql`, and
`final-reconciliation-2026-09-23`, and
`production-runtime-2026-09-23`.

## Verified this pass

- Phase 2 finish (T025-T043): durable idempotency claim/complete/tombstone,
  body-free audit, secret-safe logging/rotation, durable job store (lease/heartbeat/
  retry/dead-letter/fencing), protocol envelopes + operation-status lookup,
  lineage/source-policy, secret filter + pre-persistence gate, workspace
  containment, bounded Git observer, OAuth PKCE S256, Inbox proposals, provider
  gateway, preflight, entrypoints, Dockerfile, compose + deployment boundary
  tests, foundation evidence (`docs/acceptance/foundation.md`).
- Phase 3 US1 (T044-T055): mixed-statement intake -> 2 expenses + 1 todo with
  tomorrow 12:00-18:00 window; idempotent replay; desktop exact read 64.0000 CNY;
  grants checked before repository; migration 0002; expenses/todos/timeline/
  time_policy; life_tools + tool registry; Scenario A evidence.
- Phase 4 US2 (T056-T062): reprocessing never rewrites canonical; experience
  stays candidate; provenance explanation; migration 0003; Scenario B evidence.
- Phase 5 US3 (T063-T071): A/B/C classification, B promotion thresholds,
  explicit-outranks-inference, evidence-loss recalculation, retention boundaries,
  self_tools confirmation; migration 0004; Scenario C evidence.
- Phase 6 US4 (T072-T083): project/modules/tasks/checkpoints/finalize/recovery +
  project_tools; fresh/stale/unknown honesty; migration 0005; Scenario E evidence.
- Phase 7 US7 (T084-T090): secret corpus, workspace escape, denial-before-search,
  permission races, non-disclosure, bootstrap/incremental sync/bridge client;
  Scenario F/G/D evidence.
- Phase 8 US6 (T091-T102): asset identity/dedupe/integrity/archive safety, storage
  backend atomic promotion, processors, upload_asset; migration 0006; Scenario D
  evidence.
- Phase 9 US5 (T103-T112): intent router, permission-filtered FTS/semantic,
  RRF ranking, compiler, budget enforcement; migration 0007; Scenario G/H evidence.
- Phase 10 US8 (T113-T122): conflicts, retention, deletion plan/execution with
  version-bound confirmation, review inbox, reconciliation jobs; migration 0008;
  Scenario J evidence.
- Phase 11 US9 (T123-T129): offline honesty, ordered idempotent replay,
  conflict-to-review, pending store bounds, revoked-client stop; Scenario I evidence.
- Phase 12 US12 (T130-T136): source-preserving import, removable interface,
  optional digests; migration 0009; TRILIUM_SETUP.md; Scenario N evidence
  (real Trilium connection stays EXTERNAL_VERIFICATION_PENDING).
- Phase 13 US10 (T137-T151): doctor, growth, backup inventory/tiers, restore
  verification, health API, export manifest, maintenance schedule, deploy
  scripts (backup/verify-restore/migrate); migration 0010; Scenario K/L evidence.
- Phase 14 US11 (T152-T157): trigger registry, cooldown/merge policy, dispatch
  job, mandatory inbox; migration 0011; Scenario M evidence.
- Phase 15 Release (T158-T170): 13 documentation files, ER-12 capacity/Chinese
  search fixtures, 9-journey synthetic runtime with authoritative evidence,
  real-client matrix (PENDING), traceability matrix, final readiness review
  (0 unresolved CRITICAL).
- Phase 16 convergence (T176-T182, T184): durable deferred work above plus
  governed persisted deletion (`governed-deletion-2026-09-23.md`), runtime
  OAuth bearer identity mapping + value-free audit (`oauth-provider-hardening-
  2026-09-23.md`), and the isolated PostgreSQL migration chain.
- Phase 17 production closure (T188-T192): valid container/public bind split,
  complete file-backed Compose secrets, migration-gated production startup,
  owner/client lifecycle CLI, exact project grants, deployed API/worker/bridge
  journey, restart persistence and the 423-pass PostgreSQL regression.

## Current incomplete gates

- T186 real-client acceptance (TRAE/Cursor/ChatGPT/Trilium) is
  EXTERNAL_VERIFICATION_PENDING: live accounts and a reachable authenticated
  HTTPS/OAuth route are required; mocks never substitute.
- Off-host independent disaster backup and real-data import remain gated. The
  target-host LAN deployment is running, but do not import real personal data
  yet. The on-host encrypted backup set produced in
  this pass is a verified local restore rehearsal, not an off-host medium.

## Resume

1. Reload the TRAE CN window and visibly confirm `personal-brain` discovery;
   then provide Cursor, ChatGPT/HTTPS-OAuth and Trilium environments to finish
   T186 and update `client-matrix.md`.
2. Decide an off-host independent backup destination and verified key handling,
   then attach real-data restore verification per deployment-decision.md.
3. Any subsequent full regression must reproduce or explain drift from the
   current **423 passed / 12 skipped / 0 failed** result before
   adding claims. Never mark a skipped/PENDING item from mocks or static files.
