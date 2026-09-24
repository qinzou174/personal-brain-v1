# Red-first foundation boundary coverage

Date: 2026-09-23. This matrix describes test *coverage*, not passing behavior. The T012–T016 suites intentionally fail until their target modules exist. It does not authorize real-data intake.

| Requirement/rule | Failing test evidence |
|---|---|
| FR-005..FR-007, ER-01 | `test_validation_constraints.py`: canonical/derived authority fields, required-vs-nullable contracts, UUID/version, sensitivity/information/source classification, live source edge, uncertain confidence inputs. `test_memory_policy.py`: source-orphaning and inherited scope/sensitivity. |
| FR-012..FR-020, ER-04 | `test_time_currency.py`: numeric(20,4) one-step precision and scale edges, positive/refund/adjustment semantics, currency grouping/default-review, time source and timezone/DST ambiguity, Todo version/lifecycle/history, Event acyclicity and Relation owner boundary. |
| FR-021..FR-030, ER-02 | `test_memory_policy.py`: security/C/A/B/L0 intake priority, B promotion thresholds at and below 3 sources/14 days/2 contexts, direct user evidence, contradiction, same-source deduplication, A/C confirmation/expiry, experience candidate-only and derived access. |
| ER-03, ER-05..ER-07 | `test_validation_constraints.py`: context budgets, text/title/query/page/file/archive/offline-queue limits at max−1/max/max+1, 15-minute confirmation and 24-hour credential overlap, UUID idempotency key, retry/lease/heartbeat defaults. `test_authority_boundary.py`, `test_transactional_foundation.py`, and `test_transport_auth.py` cover deny-first, safe errors, audit exclusion, crash atomicity, replay/fencing, OAuth and stdio. |

`test_validation_constraints.py`, `test_memory_policy.py`, and `test_time_currency.py` collect as red tests; passing them is later implementation work. Story-specific physical schema, external-client, backup and end-to-end acceptance cases remain in later tasks and are not represented as complete by this matrix.
