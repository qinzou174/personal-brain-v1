# US4 Scenario E evidence: project continuity and recovery

Date: 2026-09-23 Asia/Shanghai. Synthetic data only.

## Evidence

| Requirement | Observed outcome | Evidence source |
|---|---|---|
| FR-053 fresh-client recovery | A fresh client with no chat history receives project purpose, active task, checkpoints, relevant modules, recent changes, revision/dirty evidence and a next step | `tests/acceptance/test_project_recovery.py::test_fresh_client_recovery_assembles_project_context` |
| FR-044/ER-08 freshness honesty | A module is fresh only with explicit evidence; missing evidence is `unknown`, never guessed fresh; `indexed == current` -> fresh, mismatch -> stale | `test_unknown_freshness_never_pretends_fresh`, `tests/integration/test_project_authority.py::test_revision_evidence_binds_module_state` |
| FR-048 stale warning | Stale modules carry a warning; fresh modules do not | `test_project_authority.py::test_stale_module_warns_and_fresh_module_does_not` |
| FR-041..FR-053 tool surface | start_task/checkpoint_task/get_recovery operate under `project.write:<id>` / `project.read:<id>` grants; cross-project reads denied | `tests/unit/test_project_tools.py` |
| Migration 0005 | 9 new project tables with freshness/task-state enums and dedupe keys; chain links to 0004 | `tests/migration/test_0005_project_brain.py` |

Suite result: 12 relevant tests passed across acceptance, integration, unit and
migration. Recovery timing (SC-004 <=120s) and no-history resume with replaced
client identity remain Release-phase items.

## Remaining risks

- Scenario E's stale->fresh transition after a successful incremental sync is
  implemented only at the module-freshness level; the bridge incremental sync
  (US7) is the producer that will supply the real evidence.
- Legacy project-document extraction (`bootstrap_docs`) is defined but not yet
  exercised by a real workspace scan (US7 bootstrap).
