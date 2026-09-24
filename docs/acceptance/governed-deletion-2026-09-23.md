# Governed deletion — T180 evidence (2026-09-23)

## Task marker

T180 is checked complete in `specs/001-personal-brain-v1/tasks.md`. This
document records machine-verifiable evidence produced by the current run only;
no synthetic or static-file substitution is admitted per Constitution VI.

## What T180 required

Persist confirmation, conflict, retention and deletion workflows: owner-bound
single-use versioned authorization, dependency-plan execution across
originals/derived/indexes/relations/evidence/caches, fenced reconciliation
enqueue, evidence recalculation and body-free audit outcomes.

## Implementation surface

- `AuthoritativeStore.create_deletion_plan(targets, dependents, requested_scope,
  idempotency_key)`: persists a `deletion_plans` row (`execution_state=preview`,
  `confirmation_state=pending`), a single-use version-bound `deletion_confirmation`
  review item (15-minute expiry, expected version), an `notify_review` job, a
  body-free audit event and an intake/raw record in one UnitOfWork. The plan is
  correlated to the open review item so `get_deletion_plan` can return the
  review gating state.
- `AuthoritativeStore.get_deletion_plan(plan_id)`: reads the plan plus its open
  review item.
- `AuthoritativeStore.persist_conflict(...)` / `list_conflicts()`: conflict rows
  persist to the `conflicts` table instead of process-local state.
- `AuthoritativeStore.persist_retention(...)`: retention decision records a
  body-free audit outcome under the `retention` operation.
- `AuthoritativeStore._execute_approved_deletion_plan(session, plan_id,
  requested_scope, now)`: reads the impact graph from `deletion_plans`,
  writes one `deletion_action` per target and dependent (copy-or-delete /
  recompute), tombstones originals in both reference styles (source_id
  reference and same-id `raw_inputs`), marks evidence `recomputing`, enqueues
  the fenced `reconcile_deletion` job and writes an `execute_deletion_plan`
  audit event; the plan transitions to `confirmed`/`completed`/`queued`.
- `resolve_review_item` now routes `approved`/`rejected` outcomes for
  `deletion_confirmation` items into plan execution or rejection, so
  confirmation authority remains owner-bound, single-use and version-gated.
- Production tool surface: `create_deletion_plan` (authorize `review.write` +
  `risk=high_risk_deletion`) and `get_deletion_plan` (authorize `review.read`)
  are registered in `AuthorizedToolService`, the `__main__` implemented set and
  `FR099_TOOL_NAMES`/`_TOOL_SCHEMAS`. The FR-099 surface grows from 27 to 29
  names; the contract test asserting the count was updated to 29.
- The worker `reconcile_deletion` handler (existing) consumes completed plans:
  it deletes search-index/derived-content/derivation-edge rows per the recorded
  actions and sets `reconciliation_state=completed`, giving fenced
  reconciliation across indexes/relations.

## Evidence

- Red-green integration tests: `tests/integration/test_governed_deletion.py`
  (5 tests, all passing on the current run):
  1. `test_deletion_plan_preview_is_persisted_and_review_gated`
  2. `test_rejected_deletion_plan_changes_nothing`
  3. `test_approved_deletion_executes_dependency_plan_and_enqueues_reconciliation`
     — asserts 5 recorded dependent actions, raw tombstone in both reference
     styles, evidence `recomputing`, `reconcile_deletion` job queued, audit
     `approved`.
  4. `test_reconciliation_job_cleans_search_and_derived_dependents` — executes
     the real `reconcile_deletion` handler from
     `build_job_handlers(...)["reconcile_deletion"]`.
  5. `test_conflict_and_retention_workflows_persist_domain_decisions`.
- Local regression run (current run):
  `tests/integration/test_governed_deletion.py` +
  `tests/integration/test_authoritative_store.py` + `tests/contract` +
  `tests/security` + `tests/unit` → **286 passed, 0 failed**.
- No real PostgreSQL run was repeated for T180; the sqlite `_schema`/`_seed`
  harness used here is the same reflection-based pattern already proven against
  authoritative PostgreSQL in `test_authoritative_store.py` and the
  `migration-postgresql-2026-09-23.md` suite.

## Honest state

- Deletion executes against originals/derived/indexes/relations/evidence and
  queues fenced reconciliation per FR-021..FR-030, FR-076..FR-080, SC-015.
- Real personal data was not touched. No destructive operation ran against the
  live deployment.