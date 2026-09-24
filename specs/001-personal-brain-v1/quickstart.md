# Personal Brain V1 Acceptance Quickstart

**Purpose**: Future implementation validation guide. It is not an instruction to execute code
during the current requirements-only phase.  
**Authority**: [spec.md](spec.md), [data-model.md](data-model.md), and [contracts](contracts/)

## Entry Gate

Before implementation, obtain explicit owner authorization and complete the read-only Phase 0 gate. Before final acceptance suites:

1. Phase 0 environment report exists and contains no unresolved deployment conflict.
2. Test data is synthetic and contains no real credentials or private user content.
3. Exact package/protocol versions have been checked against current official documentation.
4. The implementation provides one documented command for unit, integration, migration,
   security, acceptance, and restore suites.
5. Every test run records the implementation revision and environment identity.

The command examples below define the intended operator contract. The implementation may adjust
paths, but must preserve the named suites and expected outcomes.

## Validation Order

```powershell
# 1. Static configuration and migration preflight
uv run python -m personal_brain_server doctor --preflight --json

# 2. Unit and domain invariants
uv run pytest tests/unit -q

# 3. Contract and protocol adapter semantics
uv run pytest tests/contract -q

# 4. Canonical store and worker integration
uv run pytest tests/integration -q

# 5. Migration forward/rollback-or-restore validation
uv run pytest tests/migration -q

# 6. Permission, secret, path-boundary, and deletion safety
uv run pytest tests/security -q

# 7. Nine defining V1 journeys
uv run pytest tests/acceptance -q

# 8. Backup and isolated restore verification
uv run pytest tests/restore -q
```

No suite may be replaced by an HTTP availability check. Failures retain evidence and block the
dependent phase.

## Scenario A - Cross-Client Structured Capture (US1, FR-001..FR-020)

**Given** two active clients: mobile may write/read `knowledge`, `finance`, and `todo`; desktop may read finance and todo. Set capture time and owner timezone explicitly.

**When** mobile sends the same idempotent capture twice:

```text
午饭 38 CNY，打车 26 CNY，明天下午取快递。
```

**Then**:

- one RawInput, two Expenses, and one Todo exist; the Todo retains tomorrow's 12:00–18:00 window rather than an invented exact time;
- the duplicate request returns the original outcome;
- desktop returns exact expense and todo records with source references;
- monthly expense total increases by exactly 64 CNY;
- no semantic estimate is used for the total.

**Evidence**: canonical IDs/counts, idempotency record, exact query output, audit records.

## Scenario B - Provenance and Objective/Subjective Separation (US2)

**Given** the travel statement “今天去了京都，午饭花了 4200 日元，人太多，不过晚上特别舒服。”

**When** intake and bounded derivation finish.

**Then**:

- raw text remains byte-for-byte available to the authorized owner;
- event, expense, place, and experience are linked to the RawInput;
- “人太多” remains a contextual experience, not “用户不喜欢京都” fact;
- any preference is candidate/low-confidence with supporting evidence;
- explanation returns derivation class, evidence, time, context, confidence basis, and version.

## Scenario C - A/B/C Self-Model Policy (US3, FR-021..FR-030)

Run three fixtures:

1. “记住，以后项目时间统一北京时间” -> active explicit rule.
2. “最近挺喜欢爵士乐” -> candidate, not established.
3. “我的核心人生哲学已改变为 X” -> pending confirmation, not active.

Then explicitly contradict an inferred preference. The new explicit statement becomes current;
the old inference becomes corrected/superseded and remains historical. Deleting one evidence
item recalculates confidence without blindly deleting the claim.

## Scenario D - Asset, Archive, and Secret Safety (US6/US7)

**Fixtures**: one PDF, document, Markdown, text, image with/without embedded location, audio,
safe archive, traversal archive, expansion-bomb archive, duplicate file, and project fixture
containing `.env`, token-like content, private-key marker, and ordinary look-alike strings.

**Expected**:

- supported originals retain identity, size, hash, metadata, and processing state;
- duplicate bytes share a blob while retaining distinct source relationships;
- inferred image location is candidate; embedded location is source evidence;
- archives are listed but not broadly extracted without explicit bounded analysis;
- traversal/limit violations fail safely;
- real secret fixtures produce no searchable or logged values;
- value-free `secret_skipped` evidence exists;
- ordinary non-secret look-alikes follow the documented false-positive path.

## Scenario E - Project Continuity and Freshness (US4)

**Given** a synthetic project with project profile, two modules, active task, two checkpoints,
decision, constraint, clean revision A, then an uncommitted relevant source change in module 1.

**When** a new client with no conversation history asks “继续之前的项目”.

**Then** it receives project purpose, active task, completed/remaining work, both checkpoints,
relevant module, decision, constraint, recent changes, current revision/dirty state, and next
step. Module 1 is stale; unaffected module 2 remains fresh if its evidence supports that state.
The client is instructed to inspect current source before future modification.

## Scenario F - Workspace Containment (US7, FR-055)

From an approved synthetic workspace, attempt normalized parent traversal, absolute paths outside
the root, symlink/reparse escape, another repository, browser data, and broad home-directory
enumeration. Every attempt is rejected before file read, returns the stable boundary error, and
produces a non-sensitive audit event. Valid in-root evidence still succeeds.

## Scenario G - Permission Before Search (US5/US7)

Create a project-only client and content with strong semantic matches in project, private diary,
and finance scopes. Query broadly.

**Expected**: Only project content enters the candidate set. Denied content does not influence
rank, count, snippets, timing metadata, caches, or sources. The denial is audited without body.
Revoke the client and repeat; all protected tools fail.

## Scenario H - Retrieval Authority and Context Budgets (US5)

Run an exact finance query, todo query, current-module question, historical-rationale question,
fuzzy prior-idea query, timeline query, and self-evidence question at all three detail levels.

**Expected**:

- the router selects the documented authority for each intent;
- structured totals exactly match canonical calculations;
- current source/freshness dominates module summaries;
- historical response links decisions and change events;
- each package respects its configured budget;
- critical scope, stale, conflict, and low-confidence warnings survive compression;
- all included claims carry inspectable authorized source references.

## Scenario I - Offline Reconciliation (US9)

Disconnect a client from the authoritative Brain, submit a mutation, and require an explicit
failed or pending-sync state. Reconnect and replay it multiple times. Exactly one canonical
outcome results. Submit a conflicting version; it enters review and neither version is silently
lost. No offline acknowledgement claims durable save prematurely.

## Scenario J - Conflict and Complete Deletion (US8)

Create a canonical source with summary, embedding, relation, evidence, self claim, search entry,
and cache dependency. Request deletion.

**Expected**:

- an impact plan lists every dependent and proposed action;
- no change occurs before confirmation;
- an altered/expired plan cannot execute;
- confirmed execution removes or policy-handles each dependency;
- claim confidence is recalculated;
- search/cache removal completes before reporting final completion;
- backup-retention implications are disclosed;
- the audit event contains no deleted body.

## Scenario K - Durable Job Recovery

Accept a derivation job, stop the worker after claim, let the lease expire, restart another
worker, and replay the handler. The job reaches one terminal outcome and creates no duplicate
active derivation. Exhaust a failing fixture; it reaches dead-letter and health shows the failure
without claiming processing complete.

## Scenario L - Backup and Isolated Restore (US10)

Create a representative dataset spanning records, assets, permissions, lineage, memory,
projects, jobs, and audit. Produce a backup, restore it in isolation, and run the restore contract.

**Expected**:

- all synthetic fixture canonical counts/content and relationship/permission cases match; production sampling follows ER-10 and records its seed;
- exact queries match pre-backup results;
- permission allow/deny and revoked-client behavior match;
- all synthetic fixture asset hashes match byte-for-byte; production verification follows ER-10's full-rotation policy;
- lineage and project recovery remain navigable;
- indexes can be rebuilt;
- backup time and restore-verified time are independently recorded.

## Scenario M - Conservative Proactivity (US11)

Trigger a todo deadline, backup failure, repeated equivalent index failure, and a low-risk
preference trend. The first two create prioritized notifications; repeated equivalent failure is
merged/suppressed within cooldown; the trend remains detected but does not notify by default.

## Scenario N - Required Integration, Removable Human Interface (US12)

Import a bounded note fixture with source metadata. Disable the optional interface. Core capture,
exact records, evidence explanation, project context, retrieval, permissions, and backup remain
functional. The imported note retains its source and canonical/derived classification.

## Completion Gate

V1 is not accepted merely because services start. Acceptance requires:

- every mandatory scenario A–N above passes; optional automatic digest/transcription may be explicitly deferred with authoritative evidence;
- all nine source-defined success scenarios pass end-to-end;
- requirement-to-task coverage is 100% with no unmapped task;
- cross-artifact analysis reports zero CRITICAL findings;
- secret, permission, workspace, migration, deletion, and restore gates pass;
- documentation and operational recovery procedures match observed behavior;
- no out-of-scope capability is a dependency for a core journey.


## 扩展负例与证据

逐条FR/AC和SC样本见traceability.md，数值边界见execution-rules.md。Scenario B还须关联旅行照片；Scenario E须证明stale经成功增量刷新后变fresh，且并发变化不能误清警告。真实客户端、中文检索、provider隐私、容量性能和删除复活防护见protocol-deployment.md及tasks.md。命令只是未来入口契约，本轮未运行，亦未创建应用。
