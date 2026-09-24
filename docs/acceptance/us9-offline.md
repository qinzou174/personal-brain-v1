# US9 Scenario I evidence: offline reconciliation and honest status

Date: 2026-09-23 Asia/Shanghai. Synthetic data only.

## Evidence

| Requirement | Observed outcome | Evidence source |
|---|---|---|
| FR-087 honest offline | Unavailable mutations report `failed`/`pending_sync`, never durable save | `tests/acceptance/test_offline_reconciliation.py::test_offline_mutation_reports_honest_status` |
| FR-088/FR-011 one outcome | Replaying the same operation multiple times reconciles to exactly one authoritative outcome; conflicting versions raise for review | `test_replay_reconciles_to_one_authoritative_outcome`, `apps/bridge/.../reconcile.py` |
| FR-077/FR-088 conflict-to-review | Conflicting versions enter the review inbox with both participants preserved | `test_conflicting_version_enters_review_without_loss` |
| ER-07/FR-074 revoked stop | A revoked client stops replaying pending writes | `tests/integration/test_reconciliation_edges.py::test_revoked_client_stops_replay` |
| FR-084 crash-after-commit | Retry after a committed outcome returns the same single outcome | `test_crash_after_commit_produces_single_outcome_on_retry` |

Suite result: 5 relevant tests passed across acceptance/integration.

## Remaining risks

- The pending store is contract-defined with bounds (1000 ops/100MiB) but real
  on-disk OS-ACL + protected local key provisioning belongs to the Release
  deployment phase; the SQL pending store over an actual connection is later
  wiring.
- No real client disconnect was simulated end-to-end; this scenario's producer
  path (bridge -> Brain) is wired at the contract level.
