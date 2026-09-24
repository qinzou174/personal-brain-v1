# Phase 16 regression and reconciliation — T187 evidence (2026-09-23)

Historical snapshot: superseded by T192 and
`production-runtime-2026-09-23.md`. Current authority is 191/192 tasks and the
423 passed / 12 skipped / 0 failed PostgreSQL run.

## Task marker

T187 is checked complete in `specs/001-personal-brain-v1/tasks.md` (the task
itself is the final pass, so marking it means the pass ran and every
constitution gate above it that can run here has run).  T187's own text is
checked only for the portion that can be executed without live external
accounts; T186 remains unchecked.

## Re-run results

- Local suite (no DSN): **405 passed, 22 skipped, 0 failed**.
- With isolated PostgreSQL/pgvector (`personal_brain_20260923_test`):
  **407 passed, 11 skipped, 0 failed**; migration chain **20 passed**; real
  journeys **9 passed** (`test_real_journeys.py`).
- Skips are exclusively environment-gated (real-client accounts, optional DSN)
  and stayed skipped — never converted to passed.

## Reconciliation

- Phase 16 tasks.md count after marking this task was **186/187 checked**; T186
  remained unchecked as EXTERNAL_VERIFICATION_PENDING.
- Contradictory historical statistics removed/annotated:
  - `final-readiness-review.md` now states it is superseded by this document.
  - `traceability-matrix.md` regenerated with current-run counts (405/407,
    186/187) and per-block FR evidence links.
- Evidence ledgers updated: implementation-handoff (182→187 marker),
  convergence-status, v1-evidence-index references.

## Bidirectional requirement/task/evidence coverage

See regenerated `traceability-matrix.md`:
- 13 FR blocks → checked task groups → dated evidence documents.
- Every referenced evidence file was produced by the current run (real-journeys
  JSONL carries RUN_ID; benchmark report carries timestamp/hardware).
- No mock/placeholder/http-status reference is used as a pass claim.

## CRITICAL findings

**0 unresolved CRITICAL findings in the executed surface.** The only remaining
unverified rows are the external real-client rows in `client-matrix.md`, which
are PENDING by constitutional rule (no live TRAE/Cursor/ChatGPT/Trilium
accounts or reachable authenticated HTTPS/OAuth route in this environment), and
the ordinary backup destination being a same-host sibling directory (recorded
in `encrypted-backup-set-2026-09-23.md` as a deployment-phase constraint, not a
defect).

## Gates that remain gated (explicitly not claimed)

1. T186 real clients — EXTERNAL_VERIFICATION_PENDING.
2. Off-host independent disaster backup + real personal data import — gated on
   Phase 0 approval and US10 restore verification per deployment-decision.md.
3. Real provider/LLM traffic — not sent (no model is configured).
