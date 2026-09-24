# Feature Specification: Personal Brain V1

**Feature ID**: `001-personal-brain-v1`

**Created**: 2026-09-22

**Status**: 需求工程文档基线；最终审查见 review-report.md；产品实现未执行

**Input**: 将《工程母提示词》工程化为可追踪、可验收、可任务化的 Personal Brain V1 需求基线；本阶段只定义需求逻辑，不执行实现。

**Normative annexes**: [执行规则 ER](execution-rules.md)、[需求与验收追踪](traceability.md)、[原文覆盖](source-coverage.md)。ER 数值为可审查的工程默认，不是用户画像或实测结果。

## Product Intent and Scope

Personal Brain V1 is the user's single, long-lived digital memory and context
infrastructure. It preserves personal knowledge, structured life records, project
continuity, evidence-backed self understanding, and source-linked context independently
of any one AI model, account, IDE, or client.

V1 delivers a trustworthy core rather than every conceivable personal-AI capability. It
must prove durable capture, deterministic records, evidence-aware memory, project recovery,
permission-scoped retrieval, integrity, backup, and cross-client continuity before adding
advanced autonomy or analysis.

### In Scope

- Unified intake of notes, records, documents, assets, project state, and explicit memory.
- Structured expenses, todos, events, projects, tasks, checkpoints, decisions, constraints,
  clients, permissions, audit events, and maintenance state.
- Evidence-backed memory and self-model lifecycle with temporal history and conflicts.
- Search and context assembly that select exact, full-text, semantic, historical, or project
  retrieval according to intent while enforcing permission before retrieval.
- Local project observation, freshness detection, checkpointing, and context recovery.
- Replaceable local and remote clients using a stable tool-oriented contract.
- Conservative notifications, background processing, health, backup, restore, migration,
  integrity checking, and human review queues.
- Common documents, images, audio, and archive files with canonical originals and metadata.

### Explicitly Out of Scope for V1

- Full source-code vectorization or storing every historical source version in the Brain.
- A complex graph database, distributed event platform, microservice estate, or separate
  specialist search/vector stores without evidence that the core cannot meet a requirement.
- Full video understanding, comprehensive media analysis, or automatic aesthetic evolution.
- Automatic payment, investment, medical interpretation, personality diagnosis, or other
  high-risk autonomous action.
- Whole-computer scanning, unrestricted workspace access, or secrets management inside the
  ordinary Brain.
- High-volume proactive messaging, autonomous multi-agent societies, and complex two-way
  synchronization with human knowledge tools.
- Guaranteed cross-device recovery of uncommitted source content; V1 records its state and
  recommends a version-control checkpoint.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Capture Once, Use Anywhere (Priority: P1)

As the owner, I can capture a note, expense, todo, document, or event from one authorized
client and retrieve the same authoritative information from another authorized client.

**Why this priority**: A single durable Brain shared by replaceable clients is the core
product promise.

**Independent Test**: Capture a mixed life update from one client, then query its exact and
narrative parts from a second client with no shared chat history.

**Acceptance Scenarios**:

1. **Given** an authorized mobile client with knowledge/finance/todo write grants, owner-configured default CNY currency, and Asia/Shanghai timezone, **When** the user records “午饭 38，明天下午取快递”, **Then** the raw statement is retained and an expense and todo are available to another authorized client.
2. **Given** the same information was captured previously, **When** a new client asks for today's spending and tomorrow's todos, **Then** exact structured answers are returned from the same Brain with source references.
3. **Given** one client retries the same operation/key concurrently, **When** retries complete, **Then** only one canonical result exists; cross-client duplicates require an explicit authorized duplicate/source link rather than an implicit shared key.

---

### User Story 2 - Preserve Truth and Explain Derivations (Priority: P1)

As the owner, I can distinguish original facts and statements from AI extraction, summaries,
and inferences, and I can ask why the Brain believes a derived claim.

**Why this priority**: Long-term memory is unsafe if summaries or inference can silently
become truth.

**Independent Test**: Ingest a narrative containing an objective event and subjective
experience, inspect every derived object, and trace each one to the original input.

**Acceptance Scenarios**:

1. **Given** a retained raw travel note, **When** the Brain extracts an event, expense, place, experience, and candidate preference, **Then** every derived object identifies the raw input and its derivation class.
2. **Given** one negative experience in a crowded place, **When** the self context is queried, **Then** the Brain does not state an absolute dislike without sufficient evidence.
3. **Given** a summary or interpretation is regenerated, **When** historical derivations are inspected, **Then** the prior version remains attributable and the active version is identifiable.

---

### User Story 3 - Govern the Self Model Safely (Priority: P1)

As the owner, I can deliberately establish long-term preferences and rules while ordinary
signals remain candidates and identity-level changes require confirmation.

**Why this priority**: The self model directly affects future AI behavior and must respect
agency, change, contradiction, and explicit user authority.

**Independent Test**: Submit one explicit memory request, one casual preference, and one
identity-level change, then inspect their different states and confirmation requirements.

**Acceptance Scenarios**:

1. **Given** the user says “记住，以后项目时间统一北京时间”, **When** intake completes, **Then** an active explicit long-term rule is available to all authorized clients.
2. **Given** the user casually says “最近挺喜欢爵士乐”, **When** intake completes, **Then** it is a low-confidence candidate rather than an established identity fact.
3. **Given** a proposed change to a core value or identity statement, **When** no explicit confirmation exists, **Then** the active self model is not changed and the proposal enters review.
4. **Given** an older preference and later contradictory explicit statement, **When** both are queried, **Then** the current statement has priority and the historical one remains visible with its valid period.

---

### User Story 4 - Recover Project Work Across Accounts (Priority: P1)

As the owner, I can resume a complex project after changing AI account, client, or chat
context without reconstructing project history from scratch.

**Why this priority**: Cross-account and post-compression continuity is a defining V1
acceptance outcome.

**Independent Test**: Start and checkpoint a project task, remove conversation history, and
ask a fresh authorized client to continue the task using only Brain context and current
workspace evidence.

**Acceptance Scenarios**:

1. **Given** a task with project profile, affected modules, decisions, constraints, Git state, and checkpoints, **When** a new client asks to continue, **Then** it receives completed work, remaining work, relevant modules, decisions, constraints, recent changes, and warnings.
2. **Given** a module summary was indexed before relevant source changes, **When** it is requested, **Then** it is marked stale and cannot be presented as current fact.
3. **Given** a task is finalized, **When** its report is produced, **Then** start/end state, changed files, rationale, verification evidence, remaining work, and affected project knowledge are captured without duplicating existing decisions.

---

### User Story 5 - Retrieve the Smallest Sufficient Context (Priority: P1)

As an authorized client, I receive relevant, source-linked context for the current intent
without exposing unrelated private domains or flooding the context window.

**Why this priority**: The Brain is useful only if it returns trustworthy, scoped context
rather than the largest possible data dump.

**Independent Test**: Run exact finance, todo, semantic knowledge, historical project, and
current-module questions under different scopes and detail levels.

**Acceptance Scenarios**:

1. **Given** a finance question, **When** the client asks for a monthly total, **Then** the answer is derived from exact records rather than semantic estimation.
2. **Given** a current-module question, **When** fresh and stale project knowledge coexist, **Then** current authoritative evidence is prioritized and stale warnings are included.
3. **Given** a client lacking diary scope, **When** a broad search could match a private diary, **Then** the diary is excluded before retrieval and the denial is audited.
4. **Given** summary, normal, and deep detail levels, **When** the same question is asked, **Then** each response stays within its configured context budget while retaining source identifiers and critical warnings.

---

### User Story 6 - Store and Reprocess Assets Safely (Priority: P2)

As the owner, I can preserve original documents and media, inspect their metadata and
integrity, and reprocess them later without losing the originals or prior interpretations.

**Why this priority**: Canonical assets enable future models and durable personal knowledge.

**Independent Test**: Upload one supported file of each V1 class, inspect metadata and hash,
attempt a duplicate, and reprocess one asset with a later parser version.

**Acceptance Scenarios**:

1. **Given** a supported document, image, audio, or archive, **When** it is uploaded, **Then** the original is retained with identity, size, media type, source, integrity hash, and processing state.
2. **Given** the same content is uploaded twice, **When** hashes match, **Then** duplicate storage is avoided without discarding distinct source/evidence relationships.
3. **Given** an archive without explicit analysis approval, **When** intake completes, **Then** only the archive and a bounded basic listing are retained; its contents are not broadly indexed.
4. **Given** a better parser becomes available, **When** reprocessing occurs, **Then** new derived results become active without rewriting the original or erasing prior derivation history.

---

### User Story 7 - Enforce Client and Workspace Boundaries (Priority: P2)

As the owner, I can grant each client only the tools and data scopes it needs, revoke it,
and prove that local project access cannot escape its approved workspace.

**Why this priority**: A unified Brain concentrates sensitive information and therefore
requires enforceable boundaries.

**Independent Test**: Exercise allowed and denied scope/tool requests and workspace traversal
attempts, then inspect the resulting audit records without exposing secret content.

**Acceptance Scenarios**:

1. **Given** a project-only client, **When** it requests private diary or finance content, **Then** access is denied before search and the attempt is audited.
2. **Given** a local bridge restricted to one workspace, **When** a request attempts parent-directory traversal or another project, **Then** the read is rejected.
3. **Given** a revoked client credential, **When** it calls any protected tool, **Then** access fails and no protected content is returned.
4. **Given** source files containing credentials, **When** project bootstrap runs, **Then** secret values are neither indexed nor recorded in logs.

---

### User Story 8 - Manage Conflict, Retention, and Deletion (Priority: P2)

As the owner, I can see conflicting or changing information, apply appropriate retention,
and request complete deletion with predictable impact on dependent data.

**Why this priority**: Long-term systems accumulate change; silent overwrite and partial
deletion would destroy trust.

**Independent Test**: Create conflicting claims, supersede one, delete one evidence source,
and request deletion of a canonical item with several derivations.

**Acceptance Scenarios**:

1. **Given** incompatible claims without enough temporal evidence, **When** conflict is detected, **Then** both are preserved and the conflict enters review instead of one being silently deleted.
2. **Given** an evidence item supporting a preference is deleted, **When** deletion completes, **Then** dependent confidence is recalculated and the preference is retained, demoted, or removed according to remaining evidence.
3. **Given** an explicit deletion request, **When** impact is previewed and confirmed, **Then** canonical content and governed derivatives, relations, evidence links, indexes, and caches are handled and the outcome is auditable.
4. **Given** a completed todo or superseded preference, **When** retention processing runs, **Then** history is archived rather than silently erased.

---

### User Story 9 - Operate Through Failure and Offline Periods (Priority: P2)

As the owner, I receive honest status when the Brain is unavailable and can safely reconcile
accepted offline work after connectivity returns.

**Why this priority**: False claims of durable storage are more damaging than explicit
temporary unavailability.

**Independent Test**: Disconnect an authorized client during capture, create pending work,
restore connectivity, and reconcile the same request more than once.

**Acceptance Scenarios**:

1. **Given** the authoritative Brain is offline, **When** a client attempts a save, **Then** the client reports failure or pending synchronization and does not claim durable success.
2. **Given** pending work and restored connectivity, **When** synchronization retries, **Then** accepted items reach one authoritative final state without duplication.
3. **Given** an unreconcilable conflict, **When** synchronization runs, **Then** it enters review with both versions and no silent data loss.

---

### User Story 10 - Maintain, Back Up, and Restore the Brain (Priority: P2)

As the owner, I can see system health, detect integrity problems, back up canonical state,
and prove that recovery works in an isolated environment.

**Why this priority**: A long-lived personal memory system is not complete until loss and
corruption are recoverable.

**Independent Test**: Create a backup, restore it into isolation, validate representative
records, permissions, relationships, and asset hashes, and record the verification time.

**Acceptance Scenarios**:

1. **Given** a healthy Brain with records and assets, **When** backup completes, **Then** the backup inventory identifies all required canonical stores and configuration needed for recovery.
2. **Given** a backup set, **When** isolated restore verification runs, **Then** records, assets, relationships, permissions, and representative queries match expected invariants.
3. **Given** a missing asset, broken relation, stale module, failed job, low disk condition, or overdue backup, **When** health inspection runs, **Then** the problem is visible with severity and actionable context.
4. **Given** sustained logging and derived-data growth, **When** retention runs, **Then** bounded policies prevent unreviewed storage exhaustion.

---

### User Story 11 - Receive Deliberate, Bounded Proactivity (Priority: P3)

As the owner, I receive useful notifications for urgent V1 conditions without being
repeatedly interrupted by every detected trend or inference.

**Why this priority**: Proactivity is useful only after core truth, permissions, and
reliability are established.

**Independent Test**: Trigger a todo deadline, backup failure, repeated duplicate event, and
non-urgent preference trend, then compare notification decisions.

**Acceptance Scenarios**:

1. **Given** a todo deadline or Brain/project/backup health failure, **When** its explicit trigger fires, **Then** one prioritized notification is created through the common notification policy.
2. **Given** repeated equivalent failures, **When** notifications are evaluated, **Then** cooldown, merge, and duplicate controls prevent notification flooding.
3. **Given** a low-risk trend without a V1 notification trigger, **When** it is detected, **Then** it may be retained as evidence but does not automatically notify the user.

---

### User Story 12 - Use Human Knowledge Tools Without Dependence (Priority: P3)

As the owner, I can use a human-oriented note interface while the Brain remains complete and
operational if that interface is absent.

**Why this priority**: Human editing is valuable, but no optional client may become the
canonical core.

**Independent Test**: Import supported notes, disconnect the human knowledge interface, and
exercise core Brain capture, retrieval, memory, and project-context scenarios.

**Acceptance Scenarios**:

1. **Given** notes from a supported human knowledge interface, **When** a bounded import runs, **Then** source identity and canonical/derived distinctions are preserved.
2. **Given** the optional interface is unavailable or removed, **When** core Brain operations run, **Then** they remain available without data ownership moving to that interface.

### Edge Cases

- Duplicate submissions arrive concurrently or are replayed after an uncertain timeout.
- A raw input contains multiple currencies, relative dates, ambiguous actors, or mutually
  inconsistent facts.
- A later explicit user statement contradicts a high-confidence inference or an earlier
  explicit statement.
- A candidate preference has many observations from one low-trust source but little temporal
  diversity.
- A source is deleted while several memories, summaries, relations, or profile claims depend
  on it.
- An asset's stored bytes no longer match its recorded integrity hash.
- An archive contains traversal paths, extreme file counts, extreme expansion size, nested
  archives, binaries, or secret-like files.
- A project is not a version-controlled workspace, has a detached revision, or contains
  extensive uncommitted work.
- A project summary is fresh for one module but stale for another.
- Permission changes occur during a long-running retrieval or background job.
- A client is revoked while it has pending offline writes.
- Search finds a semantically relevant result outside the caller's authorized scope.
- Model, parser, or embedding versions change while derived work is in flight.
- Backup succeeds but a representative restore, asset check, or permission invariant fails.
- Storage becomes nearly full while intake, reprocessing, or backup is active.
- Notification triggers repeat faster than their configured cooldown.
- The owner requests destructive deletion whose full dependency impact cannot be determined.

## Requirements *(mandatory)*

### Functional Requirements

#### Authority, Intake, and Provenance

- **FR-001**: The Brain MUST provide one authoritative server-side identity and data domain shared by all authorized clients.
- **FR-002**: Clients MUST remain replaceable and MUST NOT be required to own an independent authoritative long-term memory store.
- **FR-003**: Every intake request MUST record its client, source, receipt time, declared or detected intent, and processing outcome.
- **FR-004**: The Brain MUST retain canonical raw input before producing derived objects whenever the input has lasting value.
- **FR-005**: Each stored item MUST declare whether it is canonical or derived and MUST identify its information class: fact, explicit user statement, observation, extraction, or inference.
- **FR-006**: Every persisted or decision-used derived item (as enumerated by ER-01) MUST identify its source evidence, derivation time, generating version, confidence where applicable, and current lifecycle state.
- **FR-007**: Reprocessing MUST create a distinguishable new derivation and MUST NOT rewrite canonical input or erase prior interpretation history.
- **FR-008**: The intake policy MUST support ignore, automatic save, candidate save, and confirmation-required outcomes.
- **FR-009**: Low-value acknowledgements and transient debug material MUST NOT become long-term memory by default.
- **FR-010**: Ambiguous, conflicting, or low-confidence items that cannot be safely resolved MUST enter a human-review inbox with their evidence and proposed action.
- **FR-011**: Equivalent intake retries MUST be idempotent or explicitly linked as duplicates so uncertain delivery cannot silently multiply canonical records.

#### Structured Records and Timeline

- **FR-012**: Expenses MUST retain amount, currency, category, description, occurrence time, source, and associated event when known.
- **FR-013**: Expense totals and other exact finance questions MUST use deterministic record aggregation and MUST expose currency or conversion assumptions.
- **FR-014**: Todos MUST retain content, state, due time, priority, creation/completion times, and source.
- **FR-015**: Todo state MUST distinguish pending, in progress, completed, and cancelled; terminal todos MUST be archived rather than silently deleted.
- **FR-016**: Events MUST support type, title, description, temporal bounds, importance, source, confidence, and parent/child hierarchy.
- **FR-017**: Objective occurrences and subjective experiences MUST remain distinguishable and linked by time, event, and context.
- **FR-018**: Entities MUST support at least people, places, projects, concepts, media, devices, and organizations without requiring a complex graph engine.
- **FR-019**: Relations MUST preserve typed links between records, events, entities, evidence, project objects, and assets, including their source and lifecycle.
- **FR-020**: Exact structured questions MUST be routed to deterministic lookup or aggregation before probabilistic retrieval.

#### Memory and Self Model

- **FR-021**: Memory MUST support candidate, active, temporary, historical, superseded, expired, archived, and deleted lifecycle semantics.
- **FR-022**: Retention MUST be policy-specific to the information class and MUST NOT apply a single age rule to all memories.
- **FR-023**: An explicit user request to remember information MUST create an active explicit-user-statement memory unless blocked by permission, secret policy, or the class-C confirmation precedence in ER-02.
- **FR-024**: Ordinary preference, interest, aesthetic, or behavioral signals MUST begin as candidates rather than established identity claims.
- **FR-025**: Promotion of a candidate MUST consider evidence count, time span, source trust, consistency, and contextual diversity; repetition alone MUST NOT establish it. ER-02 defines the conjunctive baseline and contradiction/confirmation blockers.
- **FR-026**: Changes to core values, philosophy, identity, major relationship definitions, or comparable long-term principles MUST require explicit confirmation bound to the proposal and version under ER-06.
- **FR-027**: Explicit user statements MUST outrank contradictory inference, while prior claims remain historical and attributable.
- **FR-028**: Self-model claims MUST support validity intervals, context, exceptions, strength, evidence, and simultaneous non-exclusive or contradictory traits.
- **FR-029**: Loss of supporting evidence MUST trigger confidence recalculation and may demote a claim without automatically erasing its history.
- **FR-030**: The Brain MUST answer “why do you believe this?” with the supporting evidence, source class, confidence basis, and applicable time/context.

#### Assets and Documents

- **FR-031**: V1 MUST preserve original PDF, word-processing document, Markdown, text, image, audio, and archive assets.
- **FR-032**: Each asset MUST retain stable identity, original name, media type, size, integrity hash, storage reference, creation time, source, metadata, and processing state.
- **FR-033**: Content identity MUST prevent redundant binary storage while preserving every distinct source, event, and evidence relationship.
- **FR-034**: Document intake MUST support bounded text extraction, searchable metadata, and derived indexing without changing the original.
- **FR-035**: Image intake MUST preserve the original, metadata, available capture time and location evidence, user annotations, tags, and bounded descriptive derivations.
- **FR-036**: Inferred image location MUST remain candidate metadata with confidence; explicit embedded location metadata may be treated as source fact.
- **FR-037**: Audio intake MUST preserve the original, duration, format, metadata, and user annotations; transcription is optional and derived.
- **FR-038**: Archive intake MUST default to preserving the archive and a bounded listing; content extraction requires explicit analysis intent and limits on paths, count, expansion size, nesting, file classes, and secrets under ER-05's concrete admission and extraction limits.
- **FR-039**: Asset integrity inspection MUST detect missing content, corruption, and hash mismatch and MUST surface affected dependents.
- **FR-040**: Asset storage location MUST be abstracted from domain identity so canonical asset references survive storage-backend migration.

#### Project Continuity

- **FR-041**: Project Brain MUST represent projects, modules, tasks, checkpoints, decisions, constraints, change events, and milestones.
- **FR-042**: A project profile MUST retain purpose, goals, principles, current technology summary, architecture summary, global constraints, deployment summary, and directory overview.
- **FR-043**: A module card MUST retain responsibility, paths, core files, interfaces, dependencies, consumers, constraints, indexed revision, relevant file evidence, and freshness.
- **FR-044**: Before any future source modification, the acting agent MUST inspect current affected source; module knowledge MUST serve navigation and context, not replace source authority.
- **FR-045**: Project bootstrap MUST respect project exclusion rules and MUST exclude dependencies, environments, build output, caches, large logs, binaries, model files, credentials, and unrelated user locations.
- **FR-046**: Existing project documents MUST be read without deletion and their extracted decisions, constraints, tasks, and profile claims MUST retain source and confidence.
- **FR-047**: Project synchronization MUST process relevant change sets incrementally after the first bootstrap rather than rescan every file by default.
- **FR-048**: Module knowledge MUST become stale when relevant current workspace evidence diverges from the indexed evidence and MUST return an explicit stale warning until refreshed.
- **FR-049**: Task lifecycle MUST distinguish planned, active, paused, completed, failed, and cancelled states.
- **FR-050**: Task start MUST capture goal, starting revision, dirty state, affected modules, plan, and constraints.
- **FR-051**: Task checkpoints MUST capture current revision, dirty and changed files, completed work, active problems, decisions, next step, and verification evidence.
- **FR-052**: Task finalization MUST compare start and end state and produce a report covering goal, revisions, changed files, module/interface impact, rationale, verification evidence, and unfinished work.
- **FR-053**: A fresh client MUST be able to recover active project context from project profile, task state, checkpoints, modules, decisions, constraints, recent changes, and current workspace evidence without prior chat history.
- **FR-054**: The Brain MUST NOT claim to preserve all uncommitted source content; it MUST distinguish observed dirty state and summaries from version-controlled recoverable content.
- **FR-055**: Local project access MUST be restricted to an explicitly approved workspace root and MUST reject traversal, unrelated projects, browser data, and broad user-directory access.

#### Retrieval and Context Compilation

- **FR-056**: Request interpretation MUST distinguish at least structured record lookup, current project state, project history/rationale, full-text discovery, semantic discovery, timeline, and self-context intents.
- **FR-057**: Retrieval ranking MUST consider semantic relevance, keyword match, recency, confidence, source trust, importance, current validity, freshness, and scope match as applicable.
- **FR-058**: Retrieval MUST progress from summaries to narrower entities and evidence to originals rather than returning all raw material by default.
- **FR-059**: Context compilation MUST perform permission enforcement, scope filtering, de-duplication, ordering, freshness checks, conflict checks, token budgeting, compression, and source-link inclusion.
- **FR-060**: Context requests MUST support bounded detail levels such as summary, normal, and deep, each with an explicit maximum context budget (ER-03: 2,000 / 6,000 / 12,000 token ceilings).
- **FR-061**: Context packages MUST separate current state, historical rationale, active work, constraints, warnings, and suggested next actions.
- **FR-062**: Current-state questions MUST prioritize current canonical evidence; historical evidence MUST supplement rather than override it.
- **FR-063**: Historical-rationale questions MUST connect prior state, decisions, tasks, changes, and current outcome.
- **FR-064**: Responses based on incomplete, conflicting, stale, or low-confidence evidence MUST include a visible qualification and MUST NOT be expressed as certain.
- **FR-065**: Every answer containing retained or derived knowledge MUST expose sufficient source identifiers for an authorized client to inspect provenance.

#### Clients, Permissions, Security, and Audit

- **FR-066**: Each client MUST have an independent identity, revocable credential state, allowed scopes, allowed tools, and last-use metadata.
- **FR-067**: Authentication, client permission, and scope filtering MUST occur before search, retrieval, or background access to protected content.
- **FR-068**: A unified Brain MUST support different permissions for different clients, including bounded read-only access.
- **FR-069**: Protected requests with missing, invalid, expired, or revoked credentials MUST fail without returning protected content.
- **FR-070**: Stored credential verifiers MUST not expose reusable credential values, and complete credentials MUST not appear in logs or audit content.
- **FR-071**: Every intake MUST distinguish normal, personal, private, highly private, and secret material. Persisted ordinary content permits only the first four; secret is a pre-persistence rejection classification (ER-05).
- **FR-072**: Secrets and secret-like values MUST be excluded from the ordinary Brain, search, derived indexes, commits, and routine logs and MUST generate a value-free exclusion record.
- **FR-073**: Audit records MUST capture client, time, requested tool/action, scope, outcome, and duration without retaining full private bodies, source code, tokens, or secret values by default.
- **FR-074**: Permission and revocation changes MUST affect new access immediately and MUST define safe handling of already-running retrievals, jobs, and pending writes.
- **FR-075**: Externally reachable access MUST expose only the authenticated Brain interface; internal data stores, workers, and administration surfaces MUST remain non-public.
- **FR-076**: Actions MUST carry risk classification, and high-risk deletion, new-recipient external communication, class-C self-model mutation, broad permission change, or destructive maintenance MUST require explicit authorization under ER-06. Ordinary A/B saves and pre-authorized owner notifications retain their specified behavior.

#### Lifecycle, Conflict, Deletion, and Maintenance

- **FR-077**: Conflicting information MUST preserve all relevant claims and relationships and MUST use conflict, supersedes, or superseded-by semantics rather than silent overwrite.
- **FR-078**: When chronology proves a change, prior information MUST become historical with an applicable validity end rather than disappear.
- **FR-079**: Explicit deletion MUST produce an impact preview across originals, derived artifacts, indexes, relations, evidence, caches, backups, and dependent confidence before irreversible action.
- **FR-080**: Confirmed deletion MUST apply the declared retention/deletion policy consistently and MUST produce a non-sensitive audit outcome.
- **FR-081**: Deterministic maintenance—including hashes, record statistics, stale detection, backup checks, and duplicate candidacy—MUST not require an AI model.
- **FR-082**: Maintenance MUST support de-duplication review, archival, memory promotion/demotion, conflict detection, stale repair, index rebuild, integrity checking, and backlog visibility.
- **FR-083**: Background work MUST have durable identity, state, attempts, timing, error summary, idempotency behavior, and a bounded retry/dead-letter policy.
- **FR-084**: Failed or uncertain background work MUST NOT cause the Brain to claim that derived content, indexing, synchronization, or persistence completed.
- **FR-085**: Schema and canonical-data migrations MUST be versioned, preceded by recoverability protection, validated afterward, and visible in health/audit evidence.
- **FR-086**: Derived content MUST retain parser/model/profile/summary version metadata sufficient for selective reprocessing.

#### Availability, Notification, and Operations

- **FR-087**: When authoritative persistence is unavailable, clients MUST report unavailable, failed, or pending synchronization rather than saved.
- **FR-088**: Pending writes MUST reconcile idempotently after reconnection and MUST surface conflicts that cannot be resolved safely.
- **FR-089**: V1 notifications MUST be limited by explicit triggers to todo deadlines, project synchronization/index failure, backup/storage failure, and Brain health failure unless the owner opts into more.
- **FR-090**: Detection of a trend or anomaly MUST remain separate from the decision to notify.
- **FR-091**: Notifications MUST pass through common priority, cooldown, merge, duplicate-suppression, and channel policies with baseline windows and owner controls in ER-11.
- **FR-092**: Health status MUST cover the Brain service, canonical store, background work, indexing, last backup, last verified restore, asset integrity, stale modules, failed jobs, review backlog, and storage capacity.
- **FR-093**: Logs, notification history, temporary artifacts, and derived indexes MUST have bounded retention or growth controls.
- **FR-094**: Backups MUST include all canonical records, assets, required configuration, relationship state, and other owner-selected authoritative sources needed to recover V1.
- **FR-095**: Backup success MUST be distinguished from restore verification; restore verification MUST validate data, relationships, permissions, queries, and asset hashes in isolation using ER-10's full-fixture and deterministic production-sampling matrix.
- **FR-096**: Backup retention MUST support configurable daily, weekly, and monthly tiers constrained by capacity rather than an unsafe fixed quantity. ER-10 defines defaults, the capacity equation, recovery-point floor, and failure behavior.
- **FR-097**: The system MUST record the last successful backup and last successful restore verification independently.

#### Interoperability and Human Interfaces

- **FR-098**: V1 MUST expose a stable, tool-oriented interface for local and remote authorized clients without embedding vendor-specific behavior in the Brain domain.
- **FR-099**: The initial tool surface MUST cover scoped context retrieval, search, note capture, self context, expenses, todos, project/module/task context, decisions, constraints, recent changes, workspace synchronization, freshness, and asset upload; overlapping tools SHOULD be consolidated.
- **FR-100**: V1 MUST integrate Trilium through a deployment or existing instance, while human knowledge interfaces remain removable clients; their loss MUST NOT disable core storage, memory, retrieval, project continuity, or authorization.
- **FR-101**: V1 human-knowledge integration MUST prefer reliable one-way import or explicitly bounded synchronization with source and conflict semantics.
- **FR-102**: Daily, weekly, or monthly digests MAY provide navigation but MUST remain derived, source-linked, and non-authoritative; incomplete digest support MUST NOT block core V1 readiness.
- **FR-103**: Client-facing rules MUST instruct agents not to save every utterance, to honor explicit memory requests, to candidate ordinary preferences, to confirm identity-level changes, to checkpoint complex work, to check freshness, to read current source before changes, and to use structured queries for structured questions.

### Key Entities

- **Raw Input**: Canonical received content with source, client, time, intent, security outcome, and processing status.
- **Knowledge Item / Document**: Human-readable canonical material and its searchable, versioned derivations.
- **Asset**: Canonical binary content plus identity, hash, metadata, storage reference, integrity, and processing history.
- **Memory**: Reusable information with class, lifecycle, validity, source, confidence, evidence, and retention policy.
- **Self Claim / Preference**: A time- and context-bound self-model assertion linked to evidence and promotion/demotion history.
- **Evidence**: A typed source contribution that supports or contradicts a derived claim.
- **Expense / Todo**: Exact structured records with domain-specific fields and lifecycle.
- **Event**: A temporal occurrence that can contain sub-events and link objective facts, subjective experiences, records, and assets.
- **Entity / Relation**: Durable real-world or conceptual object and a typed, sourced relationship between objects.
- **Project / Module**: Project context and bounded component knowledge, including current-evidence freshness.
- **Task / Checkpoint**: Work intent and resumable progress state tied to project, revision, changes, decisions, constraints, and evidence.
- **Decision / Constraint / Change Event / Milestone**: Durable project rationale, boundaries, observed changes, and significant outcomes.
- **Client / Permission / Credential State**: Replaceable consumer identity, scopes, tools, revocation, and authorization state.
- **Context Package**: A permission-filtered, de-duplicated, token-bounded response with sources, warnings, current state, history, and next actions.
- **Review Inbox Item**: An unresolved ambiguity, conflict, high-risk proposal, merge candidate, or low-confidence classification awaiting a decision.
- **Job**: Durable background work with state, idempotency, attempts, error, and timing.
- **Audit Event**: Minimal non-sensitive evidence of access or action.
- **Backup Set / Restore Verification**: Recoverable snapshot inventory and independent evidence that it can restore required invariants.
- **Notification**: A trigger-derived, prioritized, de-duplicated message governed by cooldown and channel policy.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All nine source-defined V1 success scenarios—cross-account project recovery, cross-client life records, document-plus-preference evidence, A/B/C memory handling, module staleness, context-loss recovery, permission denial, secret exclusion, and offline honesty—pass their end-to-end acceptance suites.
- **SC-002**: 100% of sampled derived claims expose an authorized path to canonical source, derivation class, generating version, and lifecycle state.
- **SC-003**: 100% of sampled exact expense and todo questions match direct canonical-record calculations; no sampled exact answer relies solely on semantic retrieval.
- **SC-004**: In the cross-account recovery scenario, a new client with no chat history retrieves every required context class and can identify the next task action within 2 minutes.
- **SC-005**: Relevant project source changes mark affected module knowledge stale before it can be returned as fresh in all tested change cases.
- **SC-006**: Every tested unauthorized scope/tool request is denied before content retrieval, produces a minimal audit event, and leaks no protected body or secret value.
- **SC-007**: Secret-filter acceptance fixtures produce zero searchable secret values, zero logged secret values, and an auditable value-free exclusion result.
- **SC-008**: Replayed intake, pending-sync, and background-work requests create exactly one canonical outcome in all idempotency test cases.
- **SC-009**: Every supported V1 asset class preserves byte-identical canonical content and passes recorded integrity verification after backup and isolated restore.
- **SC-010**: An isolated restore reproduces all sampled canonical records, relationships, client permissions, representative exact queries, and asset hashes; the independent restore timestamp is recorded.
- **SC-011**: Context packages stay within their configured detail-level budgets in 100% of successful acceptance cases (ER-03) while retaining all critical permissions, freshness, conflict, and provenance warnings.
- **SC-012**: Explicit memory, candidate preference, and confirmation-required self-model inputs reach the correct lifecycle and approval state in 100% of A/B/C policy fixtures.
- **SC-013**: No out-of-scope V1 capability becomes a blocking dependency for any of the twelve V1 user stories.
- **SC-014**: All twelve V1 user stories' acceptance scenarios have at least one requirement and one dependency-ordered task mapped to them before implementation authorization.
- **SC-015**: Every high-risk or destructive workflow includes target identification, impact preview, explicit authorization, recovery evidence, and audit outcome before it can be considered implementation-ready.
- **SC-016**: The requirements cross-review reports zero unresolved CRITICAL findings, zero untraced functional requirements, and zero untraced implementation tasks before any implementation phase begins.

## Assumptions

- The system has one primary owner in V1; multi-user collaboration and delegated household
  administration are future concerns unless separately specified.
- The target is a user-controlled long-running server plus authorized local and remote clients,
  but Phase 0 must verify the actual operating system, resources, network, existing services,
  storage, and reverse proxy before deployment design is treated as final.
- The user supplies access credentials only when a real integration step requires them; secrets
  are never embedded in requirements, plans, repositories, logs, or ordinary Brain records.
- Initial performance, promotion, retention and resource limits follow ER-02..ER-12; these are engineering assumptions with a versioned change path.
- Initial scale is personal rather than public multi-tenant scale, but data volume is long-lived
  and must support bounded growth, incremental work, backup, and migration.
- Current source and official product documentation at implementation time are authoritative for
  protocol versions, client setup, deployment syntax, and external compatibility.
- Exact service-level performance and capacity thresholds depend on Phase 0 measurements; the
  plan must define measurable budgets after the real environment is known.
- The original `工程母提示词.md` remains a preserved vision/constraint source. This specification
  is the normalized V1 requirements baseline and does not delete or rewrite that source.

## Dependencies

- A completed, read-only Phase 0 environment report before infrastructure mutation.
- A version-controlled project workspace before implementation begins.
- An owner-approved privacy/scope matrix for initial clients before real personal data is used.
- Representative non-secret fixtures for records, assets, project history, permission boundaries,
  offline reconciliation, deletion impact, and restore verification.
- Current official documentation review for every external client/protocol integrated later.

## Requirement Traceability Basis

Planning and task generation MUST preserve the stable `FR-###`, `SC-###`, and `US#` identifiers.
Every delivery task must cite one or more of these identifiers or a constitution-mandated gate.
The final cross-artifact analysis must publish a coverage table and block implementation if any
V1 mandatory requirement lacks a task or any task lacks a requirement, scenario, or governance basis.
