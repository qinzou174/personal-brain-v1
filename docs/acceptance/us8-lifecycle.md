# US8 Scenario J evidence: conflict, retention and governed deletion

Date: 2026-09-23 Asia/Shanghai. Synthetic data only.

## Evidence

| Requirement | Observed outcome | Evidence source |
|---|---|---|
| FR-077/078 conflict | Conflict resolution (time/user/tolerate) preserves every participant; no silent loss | `tests/acceptance/test_lifecycle_deletion.py::test_conflict_resolution_never_drops_participants` |
| FR-079 deletion preview | Deletion plan lists targets and dependents as preview-only; nothing changes before confirmation | `test_deletion_plan_previews_without_side_effect` |
| FR-076/FR-080 confirmation | Deletion requires confirmation; stale or unconfirmed plans raise CONFIRMATION_REQUIRED/VERSION_CONFLICT; post-delete audit contains no deleted body | `test_delete_requires_confirmation_and_stale_proposal_rejected`, `tests/security/test_deletion_privacy.py` |
| FR-079/ER-09 backup disclosure | production_purged is reported separately from backup_purge_due | `test_deletion_discloses_backup_retention` |
| FR-021/022/081/082 retention | Retention is class-specific: candidates archive at 90d, established -> historical at 180d | `test_retention_archive_expiry_policy`, `operations/retention.py` |
| FR-080/FR-084 reconciliation | Post-delete reconciliation removes search/cache and releases assets; failures surface for review | `tests/unit/test_review_reconciliation.py`, `apps/worker/.../deletion_jobs.py` |
| FR-010/026 review inbox | Owner approve/reject is single-use; participants preserved on reject | `test_review_inbox_approve_reject_single_use` |
| Migration 0008 | DeletionPlan/DeletionAction with a value-free opaque deletion ledger | `tests/migration/test_0008_lifecycle_deletion.py` |

Suite result: 9 relevant tests passed across acceptance/security/unit/migration.

## Remaining risks

- ER-09's "restore replays the deletion ledger before serving" is defined in the
  schema (opaque_deletion_version) but exercised only at unit level; the replay
  path belongs to the US10 restore gate.
- Search/cache removal is confirmed via the worker job contract; the live index
  cleanup against real FTS/pgvector remains deployment wiring.
