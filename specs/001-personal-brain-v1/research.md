# Architecture Research and Decisions (not the target-server Phase 0 report)

**Feature**: Personal Brain V1  
**Date**: 2026-09-22  
**Status**: Decision baseline; external versions require re-verification before implementation

## R-001 - Delivery Shape

**Decision**: Use a modular monolith with a server process, worker process, shared domain
package, and separately distributed workspace bridge.

**Rationale**: It creates clear security and operational boundaries while retaining one
transactional authority and avoiding premature network coordination.

**Alternatives considered**: Microservices were rejected for V1 because they add distributed
transactions, deployment dependencies, and failure modes without a current scale requirement.
A single process was rejected because asset processing and maintenance must not block request
handling and require independently visible health.

## R-002 - Canonical Data Authority

**Decision**: Use one relational canonical store for structured state, relations, jobs,
permissions, lineage metadata, and audit; treat full-text and vector representations as
rebuildable indexes.

**Rationale**: Expenses, tasks, permissions, lifecycle states, and lineage require exact
transactions. Keeping retrieval derivatives adjacent simplifies filters, backups, and deletion.

**Alternatives considered**: A vector database as primary authority was rejected because it
cannot safely answer exact record questions or own lifecycle. Separate graph and search stores
were rejected because V1 relationships and text search fit the canonical store and extra stores
complicate deletion and restore.

## R-003 - Asset Authority

**Decision**: Store canonical asset bytes in content-addressed filesystem storage keyed by
SHA-256, while the database owns identity, source relationships, metadata, integrity state, and
storage reference through a `StorageBackend` contract.

**Rationale**: This avoids database bloat, supports deduplication without deleting evidence
relationships, and permits later NAS/object-storage migration.

**Alternatives considered**: Database binary storage was rejected for operational size and
backup complexity. Hard-coded absolute paths were rejected because they prevent migration.

## R-004 - Canonical Versus Derived Records

**Decision**: Every derivation is append-versioned with source links, generator type/version,
created time, confidence, lifecycle state, and active/superseded relationship.

**Rationale**: A future parser or model must be able to reinterpret canonical history without
rewriting what was originally observed or erasing prior interpretations.

**Alternatives considered**: In-place summary updates were rejected because they destroy
explainability and make deletion/conflict behavior indeterminate.

## R-005 - Authorization Location

**Decision**: Authenticate the client, resolve allowed tools/scopes, and translate scope into
repository predicates before any search or content read. Context compilation receives only an
already-authorized candidate set and still applies output sensitivity controls.

**Rationale**: Post-search filtering can leak existence, rank, timing, logs, and cached results.

**Alternatives considered**: Application-only filtering after broad retrieval was rejected as
incompatible with the constitution. Database-only row security remains a defense-in-depth
option, not the only policy layer, because tool permissions and contextual scopes are richer
than row ownership alone.

## R-006 - Client Credentials

**Decision**: Use independent revocable credentials mapped to one owner/client authority. Static opaque credentials serve compatible local clients; remote ChatGPT integration includes OAuth authorization-code + PKCE and resource/audience validation. Credential representation and authorization flow are separate. See contracts/protocol-deployment.md.

**Rationale**: The initial single-owner system needs simple revocation and client isolation
without turning the Brain into a general identity provider.

**Alternatives considered**: Shared global tokens were rejected because one compromised client
would expose all scopes. Multi-user administration is deferred, but OAuth needed by a selected client is in V1; a single owner does not waive protocol compatibility.

## R-007 - Idempotency and Mutation Semantics

**Decision**: Every externally initiated mutation accepts an idempotency key scoped to client
and operation. Canonical transaction, outbox/job creation, and audit outcome commit together.

**Rationale**: Offline clients and uncertain timeouts will retry. Exactly-once transport is not
assumed; exactly-one canonical outcome is achieved by durable deduplication.

**Alternatives considered**: Best-effort duplicate detection by content similarity was rejected
because valid repeated records exist and retries need deterministic identity.

## R-008 - Background Work

**Decision**: Use a durable relational job table with atomic claim, lease expiry, bounded
retry, idempotent handlers, terminal dead-letter state, and observable error summaries.

**Rationale**: Personal scale does not justify a separate broker, and canonical transactions can
create work atomically.

**Alternatives considered**: In-memory queues were rejected because restarts lose accepted
work. A dedicated broker was deferred until measured throughput or isolation needs demand it.

## R-009 - Retrieval Router

**Decision**: Route structured intents to exact services first; otherwise gather authorized
full-text, semantic, timeline, project, and evidence candidates, normalize rank signals, and
compile a token-bounded package.

**Rationale**: One retrieval mode cannot safely answer exact totals, present source state,
historical rationale, and fuzzy recall.

**Alternatives considered**: “Send every question to vectors” was rejected for correctness.
Returning every matching source was rejected for privacy, latency, and context quality.

## R-010 - Self-Model Confidence

**Decision**: Store confidence inputs and policy outcomes rather than treating a floating score
as truth. Promotion considers explicitness, independent evidence, time span, source trust,
consistency, context, and contradictory evidence.

**Rationale**: A traceable policy can explain why a belief changed; an opaque score cannot.

**Alternatives considered**: Fixed “two mentions means true” thresholds and automatic identity
rewrites were rejected as manipulative and inaccurate.

## R-011 - Project Freshness

**Decision**: Store an indexed revision plus relevant path/hash evidence for each module card.
Compare it with current revision, dirty changes, and mapped relevant files before returning a
fresh state.

**Rationale**: Repository revision alone misses uncommitted work; rescanning everything on every
query is wasteful.

**Alternatives considered**: Commit-only freshness was rejected as unsafe. Time-based expiry was
rejected because age does not prove source change.

## R-012 - Deletion and Evidence Recalculation

**Decision**: Destructive deletion is a planned two-step operation: compute dependency impact
and policy actions, obtain explicit confirmation, then execute atomically where possible with
reconciliation jobs for external asset/backup effects.

**Rationale**: Canonical content can support summaries, embeddings, relations, and self claims.
Deleting only the source row leaves privacy and truth violations.

**Alternatives considered**: Cascade-all deletion was rejected because some dependent claims
must be recalculated or historically tombstoned, not blindly removed.

## R-013 - Backup and Restore Authority

**Decision**: Back up canonical database state, assets, non-secret configuration needed for
recovery, and selected external authorities; record backup success separately from isolated
restore verification.

**Rationale**: A readable backup file is not proof that a functioning, permission-correct Brain
can be restored.

**Alternatives considered**: Copying a live database data directory as the only backup was
rejected. Health checks against production alone were rejected because they do not test restore.

## R-014 - Protocol and Client Integration

**Decision**: Keep domain operations behind protocol-neutral application services, expose a
minimal tool catalog through the current official MCP-compatible adapters, and use a local
stdio bridge for workspace evidence.

**Rationale**: Clients and protocol versions change; business rules and canonical data must not.

**Alternatives considered**: Vendor-specific server logic was rejected. Dozens of narrow tools
were rejected in favor of a stable, cohesive initial catalog.

## R-015 - Observability and Privacy

**Decision**: Use structured, bounded logs and metrics with correlation IDs, object IDs, states,
durations, and value-free secret-filter events; exclude full private bodies and credentials.

**Rationale**: Operations need causal evidence without creating a second sensitive-data store.

**Alternatives considered**: Full payload logging was rejected for privacy. No logs were rejected
because background failures, access denial, and data loss could not be diagnosed.

## R-016 - Technology and Version Policy

**Decision**: Use the source-recommended Python/PostgreSQL/pgvector/Compose family as the V1
baseline, but pin exact versions only after Phase 0 and an official-document compatibility
check. Maintain a lock file and migration compatibility matrix.

**Rationale**: The engineering prompt establishes intent, but actual host architecture,
available resources, upstream releases, and client configuration are time-dependent.

**Alternatives considered**: Pinning historical versions from the prompt was rejected as stale.
Automatically taking latest versions without compatibility evidence was also rejected.

## Research Closure

Product-level defaults and boundaries are defined in execution-rules.md. Official integration findings and pending external checks are documented in contracts/protocol-deployment.md; defaults are not measured facts.
Host resources, installed services, network ownership, exact package versions, TLS/domain,
storage capacity, and backup destination remain Phase 0 facts—not unresolved product logic.
