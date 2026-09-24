<!--
Sync Impact Report
- Version change: template (unratified) -> 1.0.0
- Added principles:
  - I. One User-Owned Brain, Many Clients
  - II. Canonical Truth, Provenance, and Honest Uncertainty
  - III. Structured Data Before Probabilistic Retrieval
  - IV. Privacy, Least Privilege, and Secret Exclusion
  - V. Lifecycle Integrity, Reversibility, and Recoverability
  - VI. Incremental Delivery with Behavioral Evidence
  - VII. V1 Scope Discipline and Platform Independence
- Added sections:
  - Non-Negotiable Product Constraints
  - Requirements and Delivery Gates
- Removed sections: none (initial ratification)
- Follow-up TODOs: none
-->

# Personal Brain V1 Constitution

## Core Principles

### I. One User-Owned Brain, Many Clients

Personal Brain MUST be the single long-lived, server-side authority for the user's
personal knowledge, project context, records, memories, and derived understanding.
TRAE, Cursor, ChatGPT, mobile tools, bots, and future MCP/API consumers MUST remain
replaceable clients of the same Brain. A client MUST NOT create an independent,
authoritative long-term memory silo. Data ownership, export, backup, and migration
MUST remain under the user's control rather than an AI vendor or account.

### II. Canonical Truth, Provenance, and Honest Uncertainty

Canonical inputs MUST remain distinguishable from derived artifacts. Raw documents,
user statements, records, assets, current source code, and Git history MUST NOT be
silently replaced by summaries, embeddings, inferred profiles, or digests. Every
material derivation MUST retain `derived_from`, source identity, generation/version
metadata, and enough evidence to explain its conclusion. The system MUST distinguish
fact, explicit user statement, observation, extraction, and inference. Unknown,
conflicting, stale, or low-confidence information MUST be represented as such and MUST
NOT be presented as confirmed truth.

### III. Structured Data Before Probabilistic Retrieval

Information with stable fields, states, or arithmetic semantics—including expenses,
todos, tasks, projects, events, decisions, clients, permissions, and lifecycle state—
MUST use structured storage and deterministic queries. Exact questions MUST use exact
aggregation or lookup rather than asking semantic retrieval to guess. Full-text,
vector, graph, and AI-assisted retrieval MAY enrich discovery, but MUST NOT override
canonical structured records. Retrieval MUST be hierarchical and token-budgeted so
clients receive the smallest sufficient context package.

### IV. Privacy, Least Privilege, and Secret Exclusion

Authentication, client permission, and scope filtering MUST occur before search or
content retrieval. Each client MUST have independently revocable credentials,
allowed scopes, and allowed tools. Secrets—including passwords, tokens, cookies,
private keys, credentials, and environment-file values—MUST be excluded from the
ordinary Brain, search results, commits, and logs. Audit records MUST identify the
client, tool, scope, outcome, and timing without storing full private content or
secret values. Sensitive operations MUST default to the least privilege necessary.

### V. Lifecycle Integrity, Reversibility, and Recoverability

Memories, evidence, tasks, derived content, and assets MUST have explicit lifecycle
states and retention rules. Contradictory or superseded information MUST be preserved
as history unless the user explicitly requests deletion. Deletion MUST trace and
handle source data, summaries, embeddings, relations, evidence, and caches. Data and
schema changes MUST be recoverable through backups, recorded migrations, integrity
checks, and documented restore procedures. A successful backup claim is insufficient
without a practical restoration path and periodic restoration evidence.

### VI. Incremental Delivery with Behavioral Evidence

Work MUST proceed through a verified sequence: investigate the real environment,
freeze the relevant design intent, deliver the smallest coherent capability, verify
observable behavior, and only then expand. Every phase MUST define Given/When/Then
acceptance scenarios, failure and recovery behavior, and authoritative evidence.
Passing commands, running containers, successful writes, or HTTP success alone MUST
NOT be treated as proof that user-visible behavior is correct. Defects MUST be traced
to a cause and fixed minimally; destructive workarounds MUST NOT be the first response.

### VII. V1 Scope Discipline and Platform Independence

The Brain server MUST model clients, authentication, scopes, tools, requests, and
domain objects—not vendor-specific product assumptions. V1 MUST prefer simple,
verifiable, migratable, backed-up, recoverable, and traceable choices. V1 MUST NOT
expand into full-source vectorization, a complex graph database, comprehensive video
understanding, automated payment or investment, high-risk autonomy, full-disk
scanning, personality diagnosis, excessive proactive notification, multi-agent
societies, or complex bidirectional Trilium synchronization. Future capabilities MAY
be reserved by stable boundaries, but MUST NOT add present implementation scope.

## Non-Negotiable Product Constraints

- Current source code is the authority for present implementation; Git is the
  authority for source history; Project Brain stores understanding, rationale,
  constraints, and navigation. Project summaries and Module Cards MUST NOT substitute
  for reading current affected source before a change.
- Project knowledge MUST carry freshness evidence tied to Git state and relevant file
  changes. Stale module knowledge MUST produce an explicit warning.
- Raw intake MUST be retained according to its applicable policy. AI-derived content
  MUST be reproducible from retained canonical inputs or explicitly marked as no
  longer reproducible.
- Self-model changes MUST remain evidence-backed, temporally aware, revisable, and
  capable of representing contradiction. Explicit user statements outrank behavioral
  inference; inference MUST NOT pressure the user or masquerade as identity truth.
- Offline or partial-failure states MUST be reported honestly. If persistence is not
  authoritative, the client MUST report pending or failed synchronization rather than
  claim success.
- Assets MUST have integrity metadata. Logs and derived artifacts MUST have bounded
  growth, retention, and maintenance paths.
- External product versions and configuration procedures MUST be verified against
  current official documentation at implementation time.

## Requirements and Delivery Gates

1. The engineering master prompt is a vision and constraint source, not an executable
   plan. Before implementation, it MUST be decomposed into a testable specification,
   explicit assumptions, design decisions, contracts, and dependency-ordered tasks.
2. Every functional requirement MUST have a stable identifier, at least one acceptance
   scenario, and traceability to one or more delivery tasks. Every task MUST trace back
   to a requirement, acceptance scenario, risk control, or required design artifact.
3. Phase 0 is read-only environment investigation. It MUST produce an environment
   report before infrastructure selection or mutation. Unknown deployment facts MUST
   remain open decisions until verified on the target host.
4. Constitution compliance MUST be reviewed before and after design. A conflict with a
   MUST rule blocks planning or delivery unless the constitution is separately amended.
5. Requirements review MUST cover normal, alternate, error, recovery, security,
   privacy, deletion, migration, backup/restore, offline, stale-data, and cross-client
   scenarios where applicable.
6. Delivery plans MUST define verification at unit, integration, migration,
   permission, MCP, backup/restore, and cross-client levels when those surfaces are in
   scope. Tests MUST prove behavior and data invariants rather than mere availability.
7. High-risk or destructive operations MUST identify exact targets, recovery measures,
   and required human authorization before execution.
8. A phase is complete only when its acceptance evidence is recorded, unresolved risks
   are explicit, documentation is current, and downstream consumers observe the
   intended behavior.

## Governance

This constitution supersedes conflicting project plans, prompts, implementation
preferences, and convenience shortcuts. Amendments require a documented rationale,
an impact analysis covering affected requirements and artifacts, and an explicit
semantic version change. MAJOR changes remove or redefine non-negotiable protections;
MINOR changes add principles or materially expand governance; PATCH changes clarify
wording without changing obligations.

Every specification, plan, task set, design review, and completion review MUST check
compliance. Reviewers MUST reject unexplained exceptions, scope expansion, missing
traceability, or claims supported only by indirect evidence. Complexity beyond V1
MUST include a concrete present requirement and a simpler alternative analysis.

**Version**: 1.0.0 | **Ratified**: 2026-09-22 | **Last Amended**: 2026-09-22
