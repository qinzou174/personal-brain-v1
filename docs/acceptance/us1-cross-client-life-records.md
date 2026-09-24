# US1 Scenario A evidence: one capture, multi-client exact read

Date: 2026-09-23 Asia/Shanghai. Phase gate: Scenario A (two active clients share
canonical records). Synthetic data only; no real personal data.

## Evidence

| Requirement | Observed outcome | Evidence source |
|---|---|---|
| FR-003..FR-010 intake | Mixed statement `"午饭 38 CNY，打车 26 CNY，明天下午取快递。"` yields one RawInput identity, two Expenses and one Todo with no review items | `tests/contract/test_life_capture_contract.py::test_intake_accepts_mixed_statement_and_produces_typed_records` |
| FR-011 idempotent replay | Duplicate capture under the same key returns `status == "replay"` and the original outcome; no second canonical record | `test_duplicate_capture_returns_original_outcome_once`, `tests/integration/test_life_records.py::test_concurrent_replay_produces_one_outcome` |
| FR-012/013 exact expense | Desktop (read-only) reads exactly two expenses; total is exactly `64.0000` CNY, no semantic estimate | `test_cross_client_life_record_scenario` (`list_expense_records` total `"64.0000"`, 2 records) |
| FR-014/015 todo + ER-04 | Todo retains tomorrow's `12:00–18:00` window rather than an invented exact time | `test_cross_client_life_record_scenario` (`due_window == ("12:00", "18:00")`) |
| FR-067..FR-076 authority | A read-only client requesting an out-of-grant scope is denied before any repository read | `test_life_capture_contract.py::test_cross_client_read_requires_grant_before_returning_sources` |
| FR-099 tool surface | save_note/add_expense/get_expense_summary/add_todo/list_todos/complete_todo registered as replaceable operations | `tests/contract/test_tool_registry.py` |

Suite result: `test_life_capture_contract.py`, `test_life_records.py`, and
`test_cross_client_life_records.py` = 8 passed (8 skipped are other journeys in
the shared J02 acceptance fixture). Money/todo/time unit suite
`test_time_currency.py` = 29 passed.

## Remaining risks

- The application layer currently uses a synthetic in-memory store; the SQL
  repository and real worker/job wiring are later tasks (US1 contract passes at
  the domain/application boundary, not end-to-end persistence).
- Real-client cross-account acceptance (TRAE/Cursor/ChatGPT) stays
  EXTERNAL_VERIFICATION_PENDING until the Release phase.
- No real personal data was imported; raw-first persistence uses synthetic text.
