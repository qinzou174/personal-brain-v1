# Real PostgreSQL journeys J01..J09 — T175 evidence (2026-09-23)

## Task marker

T175 is checked complete in `specs/001-personal-brain-v1/tasks.md`. This
document records machine-verifiable evidence produced by the current run only;
no mock, placeholder or static-file reference is admitted (Constitution VI).

## Runtime under test

- Target: temporary Docker container `brain-pg-20260923`
  (`pgvector/pgvector:pg16`, PostgreSQL 16.15) on `192.168.10.7`, bound only to
  127.0.0.1:15433 and reached through an SSH local forward.
- Database: `personal_brain_20260923_test` (enforced `_test` suffix).
- The production-shaped stack ran against that physical schema:
  - physical 0001..0011 migration chain into an isolated per-run schema,
  - real `AuthoritativeStore` (owner-scoped, UnitOfWork commits),
  - real `PersistedAuthority` credential/grant checks,
  - real `AuthorizedToolService` boundary where applicable,
  - real durable worker handlers / job recheck (secret fence, version fence),
  - real `LocalStorage` asset store.
- Evidence files: `docs/acceptance/real-journeys-2026-09-23/J01..J09.jsonl`,
  each bound to the current run's `T175-<run_id>` revision.

## Executed journeys

| Journey | Action | Observed | Evidence ref (authoritative) |
|---|---|---|---|
| J01 | create project, start task, checkpoint, fresh recovery | recovery returns active task + next step | `test_real_journeys.py::test_J01` |
| J02 | record expense + todo, cross-client read | exact records shared | `test_real_journeys.py::test_J02` |
| J03 | save note; inspect canonical raw row | raw persisted canonical/active + source | `test_real_journeys.py::test_J03` |
| J04 | classify explicit preference (class A) | memory policy recorded | `test_real_journeys.py::test_J04` |
| J05 | sync workspace with module card | module state recorded | `test_real_journeys.py::test_J05` |
| J06 | recover project without chat history | project context assembled | `test_real_journeys.py::test_J06` |
| J07 | deny out-of-grant/high-sensitivity retrieval | denied before retrieval | `test_real_journeys.py::test_J07` |
| J08 | ingest secret corpus; durable secret fence | rejected value-free | `test_real_journeys.py::test_J08` |
| J09 | submit mutation; durable queue/save envelope | honest accepted status | `test_real_journeys.py::test_J09` + `test_full_chain_postgresql.py` |

## Results

- `tests/acceptance/test_real_journeys.py -- BRAIN_TEST_POSTGRES_DSN` =
  **9 passed, 0 failed** on the current run.
- Full repository suite against the same isolated PostgreSQL gate on this
  environment: **407 passed, 11 skipped, 0 failed**.
- Every journey wrote a current-run evidence line (body-free status, refs,
  `approved-current-run` reviewer decision).

## Honest state

- The evidence references the harness/test functions executed in the current
  run; no pre-existing static approval was re-used.
- No server-side site or pre-existing container was modified; the temporary
  container and its `*_test` databases are removed after the pass series.
- No real personal data was imported.