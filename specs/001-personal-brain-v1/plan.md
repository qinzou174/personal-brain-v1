# Implementation Plan: Personal Brain V1

**Feature**: `001-personal-brain-v1` | **Date**: 2026-09-22 | **Spec**: [spec.md](spec.md)

**Authorization boundary**: This plan was written during the 2026-09-22 documentation-only run.
The owner's 2026-09-23 instruction authorizes work through `tasks.md`; the concrete scope and
remaining deployment gates are recorded in `docs/acceptance/implementation-authorization.md`.

## Summary

Deliver Personal Brain V1 as a user-owned modular monolith with one canonical relational
store, content-addressed asset storage, a separate background worker process, a protocol-thin
tool interface, and a workspace-bounded local bridge. The design separates canonical facts
from versioned derivations, applies permission/scope predicates before retrieval, uses
deterministic queries for structured domains, and compiles bounded context packages from
full-text, semantic, timeline, and project evidence. Delivery proceeds by independently
testable vertical slices, beginning with Phase 0 environment investigation and the core
capture/query authority path.

## Technical Context

**Language/Version**: Python 3.12 baseline; the implementation lock file pins the latest
compatible patch versions verified at implementation time.

**Primary Dependencies**: FastAPI-style ASGI API, Pydantic v2-style validation, SQLAlchemy
2.x-style repository layer, Alembic-style migrations, official MCP Python SDK, Argon2id
credential hashing, and a PostgreSQL driver. Exact packages and versions require current
official-document verification immediately before implementation.

**Storage**: PostgreSQL as canonical structured store; PostgreSQL full-text search and
pgvector for derived retrieval; local content-addressed filesystem for canonical assets;
database-backed durable jobs; configurable backup repository.

**Testing**: pytest-compatible unit/integration/contract suites, migration round-trip tests,
property tests for authorization and lifecycle invariants, fixture-driven secret filtering,
containerized database integration tests, and isolated backup/restore acceptance tests.

**Target Platform**: User-controlled Linux server using Docker Compose; Windows-first local
workspace bridge; authenticated HTTPS remote access and stdio local access. Phase 0 must
verify the real host before these become deployment facts.

**Project Type**: Modular monolith with server API, worker, shared domain package, local
bridge, operational scripts, and documentation.

**Performance Goals**: Proposed targets using ER-12's fixed test dataset/concurrency; after Phase 0 calibration, p95 exact structured reads <= 300 ms,
p95 normal context compilation <= 2 s excluding externally hosted model latency, durable
intake acknowledgement <= 1 s for payloads accepted asynchronously, and incremental project
sync proportional to changed files rather than repository size.

**Constraints**: Personal single-owner scale; privacy-first; permission before retrieval;
canonical/derived separation; no public database/worker endpoints; honest offline status;
bounded context and storage growth; idempotent mutation; reversible migration; no V1 scope
expansion into excluded advanced capabilities.

**Scale/Scope**: Unverified sizing envelope, not a measured capacity promise: one owner, initially <= 20 clients, <= 100 projects, <= 1 million structured
objects, <= 250,000 assets, and multi-year retention. These are sizing envelopes for design
and test, not public multi-tenant service commitments.

## Constitution Check

*GATE: Document design review only, not runtime verification. Earlier PASS assertions must be interpreted with the final evidence in review-report.md.*

| Principle / Gate | Design Evidence | Result |
|---|---|---|
| One user-owned Brain | One canonical store and domain; all integrations are replaceable clients | PASS |
| Canonical truth and provenance | Canonical/derived flags, evidence links, generation versions, immutable derivation history | PASS |
| Structured before probabilistic | Exact expense/todo/task routes bypass semantic estimation | PASS |
| Privacy and least privilege | Auth -> permission -> scope predicate occurs before repository/search access | PASS |
| Lifecycle and recoverability | Explicit states, deletion impact plan, versioned migrations, backup plus restore verification | PASS |
| Incremental behavioral evidence | Vertical slices and Given/When/Then gates; availability alone is not acceptance | PASS |
| V1 scope discipline | Modular monolith and existing-store capabilities; excluded systems remain optional/future | PASS |
| Phase 0 read-only first | First delivery phase is environment report only | PASS |
| Traceability | Stable US/FR/SC IDs flow into contracts, data model, tasks, and analysis | PASS |
| High-risk authorization | Impact preview and explicit owner confirmation precede destructive work | PASS |

No exception is granted. traceability.md supplies each FR's executable acceptance scenario; document completion is not runtime acceptance.

## Architecture Boundaries

1. **Protocol adapters** authenticate a client, validate an envelope, and call application
   services. They contain no domain SQL or memory policy.
2. **Application services** coordinate use cases, idempotency, transactions, authorization,
   audit events, background-job creation, and context compilation.
3. **Domain modules** own invariants for intake, records, memory, self model, assets,
   projects, retrieval, lifecycle, notification, and operations.
4. **Repositories** apply mandatory owner/client/scope predicates and persist domain state.
5. **Derived processors** parse, summarize, embed, rank, and digest immutable canonical
   inputs; every output includes source and version lineage.
6. **Worker** claims durable jobs with leases, retry limits, and idempotent handlers.
7. **Local bridge** observes only an approved workspace root and exchanges bounded project
   evidence with the remote Brain.
8. **Operations** own migration, backup, restore verification, integrity checks, retention,
   and health without bypassing domain safeguards.

## Delivery Phases and Gates

Phase 是能力路线图；tasks.md 的编号和显式输入/输出依赖是实施顺序。秘密过滤、血缘、作业/Inbox、协议骨架前置；资产生产者在完整检索验收前完成；最小健康与备份路径先于生产写入。V1 包含全部 12 个故事（P3 只是优先级），可选仅限原文允许的转录、Digest 生成和 Gitea。

### Phase 0 - Read-Only Environment Investigation

Produce `docs/environment-report.md` from the real target host: operating system, architecture,
CPU/RAM/disk, Docker/Compose, running containers, networks, ports, reverse proxy, private
network/tunnel, database, Git, note system, backup paths, DNS/TLS, and conflicts. No install,
restart, firewall change, port binding, or secret collection is authorized. Gate: owner can
review observed facts, unknowns, risks, and proposed deployment layout.

### Phase 1 - Canonical Brain Core

Establish project skeleton, configuration boundary, canonical schema, migrations, client
identity, permission/scope policy, audit, raw intake, expenses, todos, events, and exact
queries. Gate: US1 exact life-record path and security denial path pass with idempotency.

### Phase 2 - Stable Client Contract

Expose the minimal tool catalog through remote and local protocol adapters without placing
business logic in the adapters. Gate: two independent test clients create and retrieve the
same canonical record under different scopes.

### Phase 3 - Assets and Document Intake

Add content-addressed assets, metadata, integrity, bounded document/media processing, safe
archive listing, secret filtering, full-text and semantic derivations, and durable jobs.
Gate: supported assets remain byte-identical through ingestion and restore; secrets remain
unsearchable and absent from logs.

### Phase 4 - Evidence and Self Model

Add evidence, candidates, A/B/C policy, confidence inputs, temporal validity, contradiction,
promotion/demotion, history, and explanation. Gate: US2 and US3 fixtures pass without an
inference becoming an unqualified identity fact.

### Phase 5 - Timeline, Entities, and Relations

Connect events, experiences, records, assets, entities, and typed relations in the
relational store. Gate: source-defined travel example remains factually and subjectively
separated while remaining navigable as one timeline.

### Phase 6 - Project Brain

Add project profile, module card, task/checkpoint/finalize lifecycle, decisions,
constraints, changes, milestones, and legacy-document extraction. Gate: a fresh client
recovers the active project task with provenance and without chat history.

### Phase 7 - Workspace Bridge and Incremental Sync

Add Windows-first workspace observation, path containment, Git/dirty evidence, bootstrap,
changed-file processing, module mapping, and stale/fresh transitions. Gate: traversal is
rejected and a relevant source change invalidates only affected module knowledge.

### Phase 8 - Retrieval and Context Compiler

Add intent routing, exact/full-text/semantic/timeline/project retrieval, rank fusion,
permission-aware context compilation, detail budgets, warnings, and source links. Gate:
US5 queries choose the correct authority and stay within budgets.

### Phase 9 - Additional Client Integrations

Integrate each real client against current official documentation, beginning with one local
development client and one remote client. Gate: a decision written through one client is
available to another within its scope; revocation and audit remain correct.

### Phase 10 - Human Knowledge Interface

Add reliable one-way import or narrowly bounded synchronization. Gate: disabling the
optional interface leaves core Brain behavior intact.

### Phase 11 - Operations and Long-Term Maintenance

Add health, integrity, retention, backup tiers, isolated restore verification, stale repair,
review backlog, bounded logs, and conservative notification rules. Gate: full restore and
all source-defined V1 success scenarios pass.

## Project Structure

### Documentation (this feature)

```text
specs/001-personal-brain-v1/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── tool-contracts.md
│   ├── operational-contracts.md
│   └── protocol-deployment.md
├── checklists/
│   ├── requirements.md
│   └── engineering-readiness.md
├── tasks.md
├── execution-rules.md
├── traceability.md
├── source-coverage.md
└── review-report.md
```

### Planned Source Code (future implementation; not created in this run)

```text
apps/
├── server/
│   └── personal_brain_server/
│       ├── api/
│       ├── protocols/
│       ├── bootstrap/
│       └── security/
├── worker/
│   └── personal_brain_worker/
└── bridge/
    └── personal_brain_bridge/

packages/
├── domain/
│   └── personal_brain_domain/
│       ├── intake/
│       ├── records/
│       ├── memory/
│       ├── assets/
│       ├── projects/
│       ├── retrieval/
│       ├── security/
│       └── operations/
└── infrastructure/
    └── personal_brain_infra/
        ├── persistence/
        ├── storage/
        ├── search/
        ├── jobs/
        └── models/

migrations/
tests/
├── unit/
├── contract/
├── integration/
├── migration/
├── security/
├── restore/
└── acceptance/

deploy/
├── compose/
├── proxy/
└── scripts/

docs/
```

**Structure Decision**: Keep one repository and one shared domain model, with separately
deployable server, worker, and local bridge entry points. This preserves operational
separation without introducing distributed domain ownership or premature microservices.

## Decision and Traceability Rules

- A technical choice is provisional until Phase 0 proves compatibility with the target host.
- Every schema field and state transition must cite one or more FR identifiers in migration
  notes or model documentation.
- Every tool contract must declare permission scope, idempotency behavior, canonical/derived
  effect, audit behavior, and error semantics.
- Every task must cite US/FR/SC identifiers or a constitution gate.
- Every phase closes with recorded acceptance evidence and a remaining-risk review.
- No implementation task may start during the current documentation-only objective.

## Source fidelity and external gates

source-coverage.md covers §0–144 including source Phase 0–13 and exact documentation outputs. Target-server investigation is still pending; this desktop analysis cannot replace it. No Git branch was created.

Deployment includes Linux Compose manifests, API/worker builds, internal PostgreSQL/pgvector networking, persistent assets/DB/Trilium/backups, bounded logs, readiness and reconnect, proxy reuse and rollback. Server scripts use Linux shell/Python; local Windows bridge setup may use PowerShell. Real TRAE CN, Cursor and ChatGPT must have account/version and interaction evidence; unavailable integrations stay EXTERNAL_VERIFICATION_PENDING.

## Post-Design Constitution Re-check

Phase 1 design artifacts preserve one authority, lineage, structured routing, pre-query
authorization, explicit lifecycle, recoverability, incremental delivery, and V1 exclusions.
No gate requires an exception, so Complexity Tracking is intentionally empty.


## 前置与完成边界澄清

正式tasks.md已按真实依赖重排为170项；本节Phase0–11是能力路线图，不是任务执行序号，源Phase0–13映射见source-coverage.md。US11/US12仍必需；Trilium集成先于完整US10备份/恢复，通知在US10健康能力后完成；Trilium在线不是核心依赖，自动Digest/转录可选。

共享schema/lineage、secret、Inbox、协议认证、最小Git观察及provider出站限制在US1之前；Event/Relation/Experience由US1创建，完整解释在US2；Asset/SearchIndexEntry由US6创建，Context表在后续US5迁移。实体只创建一次。真实个人数据部署必须等US10恢复验证，MVP仅合成数据。所有创建/部署任务仍待明确实施授权。
