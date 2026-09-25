# Tool Contracts

**Purpose**: Protocol-neutral V1 contract. MCP/HTTP/stdin adapters map to these operations but
must not change domain semantics.  
**Traceability**: FR-001..FR-103, especially FR-056..FR-076 and FR-098..FR-103.

## Common Request Envelope

Every operation receives an authenticated client context plus:

```text
request_id         opaque correlation identifier
idempotency_key    required for mutations; absent for pure reads
requested_scope    explicit scope or bounded list
detail_level       summary | normal | deep (reads only)
expected_version   optional optimistic concurrency version
payload            operation-specific validated input
```

The adapter must not accept credentials inside `payload`. Effective scope is derived from
client grants and may be narrower than requested scope.

## Common Success Envelope

```text
request_id
status             completed | accepted | pending_confirmation | pending_sync
result              operation-specific result or durable job reference
source_refs         authorized provenance identifiers
warnings            stale | conflict | incomplete | low_confidence | partial
audit_ref
```

`accepted` means durable canonical or job acceptance, not derived processing completion.
`pending_sync` never means authoritative save.

## Common Error Envelope

```text
request_id
status             rejected | failed | unavailable | conflict
code               stable machine-readable code
message            safe human-readable explanation
retryable          boolean
retry_after         optional
details             bounded non-sensitive validation/conflict data
audit_ref           when policy permits
```

Errors must not reveal existence of out-of-scope content. Credential, secret, private body,
raw stack, query plan, and unrelated path values are forbidden.

## Read Operations

| Operation | Required tool/scope | Input | Output | Authority |
|---|---|---|---|---|
| `get_brain_context` | `context.read`, requested domain scopes | intent, detail, optional time/project | ContextPackage | compiled authorized evidence |
| `search_brain` | `search.read`, requested scopes | query, filters, detail, limit | ranked source-linked hits | routed exact/FTS/semantic |
| `get_entry_content` | `search.read` on the *entry's own scope* | entry_id, sensitivity ceiling | full source text plus metadata | honest `NOT_FOUND` on absence (unknown / above ceiling / tombstoned source) |
| `get_self_context` | `self.read` | categories, time, detail | active plus relevant history/evidence | explicit statements and evidence policy |
| `get_expense_summary` | `finance.read` | period, currencies, grouping | exact totals and assumptions | canonical Expense records |
| `list_todos` | `todo.read` | states, due range, priority | exact Todo records | canonical Todo records |
| `get_project_context` | `project.read:<id>` | project, detail, intent | project ContextPackage | current project evidence plus history |
| `get_module_context` | `project.read:<id>` | module, detail | ModuleCard, freshness, sources | current workspace evidence dominates |
| `search_project` | `project.read:<id>` | project, query, filters | authorized project hits | current/history intent routing |
| `get_active_task` | `project.read:<id>` | project | active task and checkpoints | canonical task state |
| `get_recent_changes` | `project.read:<id>` | project/module, since, limit | ChangeEvents and evidence | current/historical distinction |
| `check_freshness` | `project.read:<id>` | project/module | fresh/stale/unknown plus reason | indexed vs current evidence |

Read operations are side-effect free except minimal audit and last-use metadata. A denied read
must produce no search/index access for the denied scope.

`search.read` and `context.read` are granted per requested scope: a client may search or compile
context for exactly the content scopes it already holds (`knowledge`, `finance`, `todo`, `self`,
`asset`, and each explicitly granted `project:<id>`). The grant never widens a client's scope set.
Exact routing inside `search_brain` (expense totals, todo lists) stays inside the already-authorized
scope and returns canonical domain records without re-checking a different domain tool, so the
operation is governed by exactly the tool named above. `answer_brain` is governed by `search.read`
like `search_brain` (retrieval plus a grounded model summary): authorizing it as `knowledge.read`
denied every scope except knowledge while `search_brain` succeeded (fixed 2026-09-24).
`get_entry_content` resolves the entry first and then authorizes `search.read` on the row's own
scope — the caller declares no scope, so authorization can never be widened by request input.

## Mutation Operations

| Operation | Required tool/scope | Required input | Canonical effect | Async effect |
|---|---|---|---|---|
| `save_note` | `knowledge.write` | content/source/time/sensitivity | RawInput and knowledge identity | extraction/index jobs |
| `update_note` | `knowledge.write` | old note ID + corrected content (2026-09-25, 003-correction-delete-ux) | new RawInput; old raw tombstoned and its retrieval card removed in the same transaction | extraction/index jobs; response names `superseded_id` |
| `add_expense` | `finance.write` | exact amount/currency/description/time | RawInput + Expense | optional categorization candidate |
| `correct_expense` | `finance.write` | expense ID + new amount (2026-09-25, 003-correction-delete-ux) | old expense tombstoned; corrected canonical row (`更正` prefix, version = old + 1); summary counts active rows only | index job for the corrected source; response carries `corrected_from` |
| `add_todo` | `todo.write` | content/source; optional due/priority | RawInput + Todo | deadline candidate |
| `complete_todo` | `todo.write` | todo ID/version/completed time | Todo state transition | archive/notification update |
| `delete_todo` | `todo.write` | todo ID/version (2026-09-25, 003-correction-delete-ux) | Todo tombstone (`lifecycle_state=deleted`); retrieval card removed in the same transaction; double delete → `NOT_FOUND`, stale version → `VERSION_CONFLICT` | index job settles as declared skip |
| `start_task` | `project.write:<id>` | goal, project, plan, constraints, workspace evidence | active ProjectTask | context/index update |
| `checkpoint_task` | `project.write:<id>` | task/version, progress, problems, next, verification, workspace evidence | append-only Checkpoint | module/change analysis |
| `finalize_task` | `project.write:<id>` | task/version, outcome, verification, remaining work | terminal task report | module refresh/change derivation |
| `record_decision` | `project.write:<id>` | statement, rationale, evidence, affected scope | Decision | context/index update |
| `record_constraint` | `project.write:<id>` | statement, rationale/source, affected scope | Constraint | context/index update |
| `sync_workspace` | `project.sync:<id>` | approved-root proof, revision/dirty/change evidence | WorkspaceObservation | bounded module refresh jobs |
| `upload_asset` | `asset.write` | metadata plus streamed bytes | Asset and AssetBlob identity | bounded parse/index jobs |

All mutations require an idempotency key. A replay with the same client, operation, key, and
equivalent payload returns the original outcome. A different payload under the same key returns
`IDEMPOTENCY_CONFLICT` and creates no new canonical state.

Advisory response fields (2026-09-25, 003-correction-delete-ux; never blocking, never hiding a
failure): `index_state: "pending"` on card-producing writes (the retrieval card is built by a
durable job seconds later), `conflict_warning` on `propose_self_claim` (same-category
opposite-polarity claim exists, shared polarity rule with the nightly `conflict_scan`),
`duplicate_name_hint` on `create_project` (a live same-name project exists). `resolve_review_item`
on a non-open item returns the stable `ALREADY_RESOLVED` code — an idempotent state, not a missing
confirmation.

## Confirmation-Gated Operations

The following are two-step workflows, not ordinary direct mutations:

- Activate a class-C identity/value change.
- Delete canonical or high-impact data.
- Broaden client permissions or sensitivity ceiling.
- Send an external message or initiate other high-risk action added later.

Step 1 creates a versioned impact proposal with risk, evidence, dependents, and expiry. Step 2
requires the proposal ID, unchanged version, explicit owner confirmation, and idempotency key.
Expired or changed proposals must be regenerated.

## Stable Error Codes

`AUTH_REQUIRED`, `AUTH_INVALID`, `CLIENT_REVOKED`, `TOOL_DENIED`, `SCOPE_DENIED`,
`SENSITIVITY_DENIED`, `VALIDATION_FAILED`, `NOT_FOUND`, `VERSION_CONFLICT`,
`IDEMPOTENCY_CONFLICT`, `CONFIRMATION_REQUIRED`, `CONFIRMATION_EXPIRED`,
`STALE_PROJECT_CONTEXT`, `SECRET_REJECTED`, `PAYLOAD_TOO_LARGE`, `ARCHIVE_LIMIT_EXCEEDED`,
`WORKSPACE_BOUNDARY_VIOLATION`, `BRAIN_UNAVAILABLE`, `JOB_ACCEPTED`, `DEPENDENCY_CONFLICT`,
and `INTERNAL_SAFE_ERROR`.

## Contract Invariants

1. Search is never called before effective scope is established.
2. A source reference is returned only if the client can read the source.
3. Exact record operations never derive totals from embeddings or prose.
4. `completed` never describes an uncommitted or merely queued canonical mutation; committed mutations also return `persistence=canonical_committed`.
5. Stale, conflicting, incomplete, or low-confidence evidence is visible in warnings.
6. Protocol adapters must preserve these semantics and may only narrow access or output.


## 必须合读的补充约束

[协议/部署契约](protocol-deployment.md)补充OAuth、传输、中文检索、asset_handle上传、owner review/health/notification/status/export入口；[ER](../execution-rules.md)定义值域和上限。工具grant与domain scope、sensitivity必须同时满足；save_note跨域抽取须分别具备目标域write grant。预授权owner通知按ER-11不逐次确认，新收件人发送不在V1自动行为范围。
