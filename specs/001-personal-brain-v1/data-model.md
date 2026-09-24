# Personal Brain V1 Data Model

**Purpose**: Logical model and invariants for planning; physical schema names may change but
the concepts and constraints are mandatory.  
**Requirements**: [spec.md](spec.md)

## Global Conventions

All primary entities use an opaque stable identifier and UTC `created_at`/`updated_at`.
User-facing local times retain the original timezone/offset when known. Mutable entities carry
a concurrency version. Soft lifecycle state is not a substitute for an explicit, confirmed
deletion workflow.

Every information-bearing object includes:

- `owner_id`: one V1 owner boundary; reserved for future expansion.
- `sensitivity`: `normal | personal | private | highly_private`; `secret` exists only in pre-persistence filtering (ER-05).
- `information_class`: `fact | explicit_user_statement | observation | ai_extraction | ai_inference`, distinct from source carrier.
- `canonicality`: `canonical | derived`.
- `source_kind`: `explicit_user_statement | original_document | system_fact | observation |
  ai_extraction | ai_inference`.
- `source_id`: canonical source or intake identity.
- `valid_from`, `valid_to`: temporal truth bounds when applicable.
- `lifecycle_state`: domain-specific state.
- `deleted_at`: only after governed deletion; tombstone metadata must not retain deleted body.

Derived entities additionally require `generator_kind`, `generator_version`, `derived_at`,
`confidence` when uncertain, and at least one `DerivationEdge`. (FR-005..FR-007, FR-086)

## Authority and Intake

### Client

Fields: `client_id`, display name, client type, status (`active | suspended | revoked`),
scopes, allowed tools, permission_epoch, created/last-used/revoked times. Separate Credential rows carry credential_id, client_id, verifier, issued_at, expires_at, revoked_at and overlap deadline. OAuthGrant records issuer, oauth_client_id, audience, owner/client mapping, scopes, grant expiry and revocation; reusable credentials are not ordinary content. The credential value is never stored. A revoked client cannot regain access by
reusing an older token. (FR-066..FR-070)

### PermissionGrant

Fields: grant ID, client ID, effect (`allow | deny`), scope pattern, tool pattern, sensitivity
ceiling, effective interval, issuer, reason. Explicit deny wins; the most restrictive
sensitivity ceiling applies. Authorization is evaluated before repository access. (FR-067..FR-075)

### IntakeRequest

Fields: request ID, client ID, idempotency key, received time, content reference, detected and
declared intent/type, requested scope, security decision, intake level (`L0 | L1 | L2 | L3`),
state (`received | accepted | pending_confirmation | processing | completed | rejected |
failed`), outcome references, correlation ID, error code. Unique `(client_id, operation,
idempotency_key)` guarantees one canonical outcome. (FR-003, FR-008..FR-011)

### RawInput

Fields: raw input ID, immutable content or asset reference, content hash, original time and
timezone, source channel, client ID, language, sensitivity, retention policy, canonical state.
Body changes create a new RawInput; canonical content is not updated in place. (FR-004..FR-007)

### DerivationEdge

Fields: edge ID, source object type/ID, derived object type/ID, role (`extracted_from |
summarized_from | embedded_from | inferred_from | supported_by | contradicts`), contribution
weight if applicable, generator version, created time. A derived object cannot be active without
at least one live source edge. Losing all sources makes it orphaned and excludes it from answers; active and orphaned are mutually exclusive (ER-01). (FR-006, FR-007, FR-029, FR-030)

## Knowledge, Assets, and Search

### Document

Fields: document ID, raw input or asset ID, title, document type, canonical text/reference,
language, source metadata, current extraction ID, retention. Extracted text is derived if the
asset is canonical. (FR-031, FR-034)

### Asset

Fields: asset ID, content blob ID, original name, media type, size bytes, SHA-256, storage
backend/key, source, user metadata, capture time/location evidence, integrity state (`unknown |
valid | missing | corrupted | hash_mismatch`), processing state (`stored | queued | processing |
ready | partial | failed`), retention. SHA-256 and size identify binary content but do not merge
distinct source/evidence records. (FR-031..FR-040)

### AssetBlob

Fields: blob ID, SHA-256, size, backend/key, reference count, first-seen time, last integrity
check. Unique `(sha256, size)` prevents duplicate bytes. A blob is removable only when no live
Asset or pending-deletion reference requires it. Backup snapshots retain independent bytes and cannot hold a production copy alive after deletion (ER-09).

### DerivedContent

Fields: derivation ID, target type/ID, kind (`extracted_text | summary | embedding |
description | transcript | digest | archive_listing`), version, model/parser identity,
confidence, payload or storage reference, state (`candidate | active | superseded | failed | orphaned | recomputing`), created time. At most one active derivation per target/kind/version policy; prior
versions remain attributable. (FR-034..FR-038, FR-086, FR-102)

### SearchIndexEntry

Fields: entry ID, target identity, authorized scope, sensitivity, canonical/derived flag,
validity, freshness, searchable text, vector/model version, metadata filters, indexed time.
It is rebuildable and excluded from canonical backup-completeness counts. Secret sensitivity is
invalid for ordinary search entries. (FR-056..FR-065, FR-072)

## Structured Life Data

### Expense

Fields: expense ID, amount (exact decimal), ISO currency, category, description, occurred time
and timezone, source ID, optional event ID, lifecycle. Amount must be positive unless a clearly
typed refund/adjustment policy applies. ER-04 fixes numeric(20,4), mandatory currency, refund kind, relative-date ambiguity and corrections. Cross-currency totals must not silently combine amounts
without an explicit conversion basis. (FR-012, FR-013)

### Todo

Fields: todo ID, content, state (`pending | in_progress | completed | cancelled`), due time and
timezone, due-window start/end/precision, priority, created/completed times, source ID, archived time. Both pending and in_progress can complete directly; terminal correction is a versioned event (ER-04). (FR-014, FR-015)

### Event

Fields: event ID, type, title, objective description, subjective experience reference, start/end
time and timezone, importance, source ID, confidence, parent event ID, lifecycle. Parent/child
relationships must be acyclic and contained within the owner boundary. (FR-016, FR-017)

### Experience

Fields: experience ID, event ID, user expression, normalized interpretation (derived), context,
source ID, confidence, valid time. It cannot directly establish a global preference without a
separate evidence/promotion decision. (FR-017, FR-024..FR-030)

### Entity and Relation

Entity fields: entity ID, type (`person | place | project | concept | media | device |
organization | extensible`), canonical name, aliases, source, confidence, lifecycle.

Relation fields: relation ID, subject type/ID, predicate, object type/ID, source, confidence,
valid interval, lifecycle. Both endpoints must exist; relations are typed and cannot cross owner
boundaries. (FR-018, FR-019)

## Memory and Self Model

### Memory

Fields: memory ID, kind, statement, lifecycle (`candidate | active | temporary | historical |
superseded | expired | archived | deleted`), source class, confidence, confidence inputs,
retention policy, valid interval, context, exceptions, strength, superseded-by ID. (FR-021..FR-030)

### SelfClaim

Fields: self claim ID, category (`preference | aesthetic | value | working_style |
communication_style | interest | habit | goal | philosophy`), claim, policy class (`A | B |
C`), lifecycle (the eight Memory states), establishment (`candidate | established | explicit`), review (`none | pending_confirmation | rejected`), correction events, confidence inputs, evidence summary, valid interval, context,
exceptions, confirmation identity/time. Class C cannot enter active state without explicit
confirmation. (FR-023..FR-030)

### Evidence

Fields: evidence ID, target memory/self-claim ID, source object type/ID, stance (`supports |
contradicts | neutral`), source trust, observed time, context, contribution, lifecycle. Deleting
or invalidating evidence queues recalculation. Multiple links may point to one source without
duplicating it. (FR-025, FR-029, FR-030)

### Conflict

Fields: conflict ID, participating object references, conflict type, detected time, evidence,
state (`open | resolved_by_time | resolved_by_user | tolerated | superseded`), resolution and
resolver. Resolution never silently deletes participants. (FR-077, FR-078)

## Project Brain

### Project

Fields: project ID, name, purpose, goals, principles, technology/architecture/deployment
summaries, global constraints, directory overview, workspace identity, repository identity,
current revision evidence, lifecycle. (FR-041, FR-042)

### ModuleCard

Fields: module ID, project ID, name, paths, responsibility, core files, interfaces,
dependencies, consumers, constraints, indexed revision, relevant file hashes, freshness
(`fresh | stale | unknown`), stale reasons, refreshed time. A relevant source change moves
`fresh -> stale`; only successful bounded refresh moves `stale/unknown -> fresh`. (FR-043..FR-048)

### ProjectTask

Fields: task ID, project ID, goal, state (`planned | active | paused | completed | failed |
cancelled`), start/end revision, start/end dirty state, plan, constraints, affected modules,
started/completed times, remaining work, final report. Only one owner-declared primary active
task per project unless concurrency is explicit. (FR-049..FR-054)

### Checkpoint

Fields: checkpoint ID, task ID, revision, dirty files, changed files, completed work, problems,
decisions, next step, verification evidence, captured time. Checkpoints are append-only; a
correction creates a new checkpoint. (FR-051)

### Decision, Constraint, ChangeEvent, Milestone

Each has project/module/task links, statement, rationale or evidence, source, validity/lifecycle,
and deduplication key. Decisions can supersede but not erase history. Change events identify
affected modules and revisions. (FR-041, FR-046, FR-052, FR-053)

### WorkspaceObservation

Fields: observation ID, project ID, approved root identity, revision, branch/ref, dirty state,
changed paths, diff summary, file hashes, observed time, bridge client. Paths must be normalized,
contained within the approved root, and never store unrelated absolute user paths. (FR-045,
FR-047, FR-048, FR-054, FR-055)

## Retrieval and Delivery

### ContextRequest

Fields: request ID, client ID, intent, requested scopes, detail level (`summary | normal |
deep`), token/size budget, query, target project/module/time range, correlation ID. Authorized
effective scopes are recorded separately from requested scopes. (FR-056..FR-060)

### ContextPackage

Fields: package ID, request ID, intent, current state, historical rationale, active task,
relevant objects, decisions, constraints, recent changes, warnings, suggested next actions,
source references, used budget, generated time. Critical permission/freshness/conflict warnings
cannot be dropped merely to meet a budget; content must be reduced instead. (FR-059..FR-065)

### ReviewInboxItem

Fields: item ID, type (`ambiguity | conflict | merge_candidate | profile_confirmation |
deletion_confirmation | permission_change | failed_reconciliation`), subject references,
proposal, risk, evidence, state (`open | approved | rejected | deferred | resolved`), resolver,
resolution time. (FR-010, FR-026, FR-076..FR-080)

## Operations

### Job

Fields: job ID, type, payload reference, idempotency key, state (`queued | leased | succeeded |
retry_wait | dead_letter | cancelled`), priority, attempts/max attempts, available time, lease
owner/expiry, started/finished times, error code/summary, result references. An expired lease may
be reclaimed; handlers must tolerate replay. (FR-083, FR-084)

### AuditEvent

Fields: audit ID, client ID, correlation ID, action/tool, effective scope, target category/ID,
outcome, error code, duration, time, risk, authorization decision. Private body, source body,
credential, and secret fields are forbidden. (FR-070, FR-073, FR-076, FR-080)

### DeletionPlan

Fields: plan ID, requested targets, impact graph summary, policy action per dependent, backup
implications, risk, created time, confirmation state, confirmation identity/time, execution
state, reconciliation state, audit reference. Execution requires an unchanged plan version and
valid explicit confirmation. (FR-079, FR-080)

### BackupSet and RestoreVerification

Backup fields: backup ID, inventory, covered canonical revision/time, database artifact,
asset manifest, configuration manifest, retention tier, state, integrity result, completed time.

Restore verification fields: verification ID, backup ID, isolated target identity, restored
record counts, relationship checks, permission cases, representative queries, asset hashes,
result, failures, verified time. Backup success does not imply restore success. (FR-094..FR-097)

### Notification

Fields: notification ID, trigger type, source object, risk/priority, dedupe key, cooldown group,
channel, state (`candidate | suppressed | queued | delivered | failed | acknowledged`), reason,
created/delivered time. Detection creates a candidate; policy creates or suppresses delivery.
(FR-089..FR-091)

### HealthFinding

Fields: finding ID, component/category, severity, status, first/last seen, evidence summary,
affected object references, remediation guidance, acknowledgement/resolution. Health includes
services, store, jobs, indexes, assets, freshness, backlog, backup/restore, and capacity.
(FR-092, FR-093)

## Deletion and Retention Invariants

1. Ordinary lifecycle transitions preserve history; only an explicit authorized deletion plan
   can remove governed content. (FR-021, FR-077..FR-080)
2. A deletion plan must classify each dependent as delete, detach, tombstone, recompute,
   supersede, retain-by-obligation, or manual review.
3. Search and cache removal must precede reporting deletion complete; asynchronous external
   cleanup remains visibly pending.
4. Backup expiration follows declared retention; the user must be informed when a deleted item
   remains in unexpired backups and how it ages out.
5. Secret material is rejected before ordinary persistence; a value-free audit marker is not
   considered retention of the secret. (FR-072)

## Relationship Summary

```text
Client -> PermissionGrant -> IntakeRequest -> RawInput
RawInput/Asset -> DerivationEdge -> DerivedContent/SearchIndexEntry
RawInput -> Expense/Todo/Event/Experience/Memory
Memory/SelfClaim <- Evidence -> canonical sources
Project -> ModuleCard/ProjectTask/Decision/Constraint/ChangeEvent/Milestone
ProjectTask -> Checkpoint
WorkspaceObservation -> Project/ModuleCard freshness
ContextRequest -> authorized candidates -> ContextPackage
Canonical entities -> DeletionPlan -> recalculation/cleanup jobs
BackupSet -> RestoreVerification
Trigger -> Notification candidate -> policy outcome
```

## Normative validation constraints

ER-01..ER-13 define state transitions, scope inheritance, admission, numeric/time constraints, timeouts, leases, deletion and restore sampling. Each task consuming an entity also consumes these constraints. Text request envelope ≤1 MiB, titles ≤512 characters, pagination limit 1..100 (default 20), query ≤8,000 characters, IDs opaque UUIDs; nullable times mean unknown, never epoch zero. owner_id/source_id resolve in the authorized scope. Imported instructions remain data, never proof of user authorization.
