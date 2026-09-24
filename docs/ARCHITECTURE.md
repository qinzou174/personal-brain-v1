# Personal Brain V1 - Architecture

## Overview

Modular monolith with one canonical relational store, content-addressed asset
storage, a separate background worker, a protocol-thin tool interface, and a
workspace-bounded local bridge. Canonical facts are separated from versioned
derivations; permission/scope predicates run before retrieval.

## Components

1. **Protocol adapters** authenticate a client and call application services;
   no domain SQL or memory policy lives here.
2. **Application services** coordinate use cases, idempotency, transactions,
   authorization, audit and background-job creation.
3. **Domain modules** own invariants for intake, records, memory, self model,
   assets, projects, retrieval, lifecycle, notification and operations.
4. **Repositories** apply owner/client/scope predicates and persist domain state.
5. **Derived processors** parse, summarize, embed, rank and digest immutable
   canonical inputs; every output carries source and version lineage.
6. **Worker** claims durable jobs with leases, retries and idempotent handlers.
   A built-in daily scheduler (`personal_brain_worker/scheduler.py`) enqueues the
   periodic work (digest, candidate promotion, retention, conflict scan, health)
   exactly once per owner and local day, so the backend evolves without user
   interaction.
7. **Local bridge** observes only an approved workspace root.
8. **Operations** own migration, backup, restore verification, integrity checks,
   retention, health and growth without bypassing domain safeguards.

## Data authority

- Structured before probabilistic: exact expense/todo/project routes bypass
  semantic estimation.
- Canonical/derived separation: derived content links to immutable sources and
  orphans when the last live source is lost.
- Permission before retrieval: denied scopes never enter search candidates.

## Packages

`packages/domain/personal_brain_domain` (domain), 
`packages/infrastructure/personal_brain_infra` (persistence/storage/search/jobs),
`apps/server/personal_brain_server` (API), `apps/worker/personal_brain_worker`,
`apps/bridge/personal_brain_bridge`, `migrations`, `deploy`.
