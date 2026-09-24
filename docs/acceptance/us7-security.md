# US7 Scenario F/G/D evidence: workspace security and incremental bridge

Date: 2026-09-23 Asia/Shanghai. Synthetic data only.

## Evidence

| Requirement | Observed outcome | Evidence source |
|---|---|---|
| FR-072 secret corpus | Filename/type/content secret corpus is rejected before ordinary storage with value-free results | `tests/acceptance/test_security_boundaries.py::test_secret_corpus_never_enters_ordinary_storage` |
| FR-055 workspace escape | Parent-traversal, absolute-path and lexical attacks are rejected before any file read | `test_workspace_escape_rejected_before_read`, `tests/unit/test_workspace_boundary.py` |
| FR-020 denial-before-search | Unauthorized query never touches the candidate set; denial is raised first | `test_denial_before_search_no_candidate_access`, `tests/security/test_permission_races.py` |
| FR-074 permission races | Permission epoch change blocks new requests immediately; running workers holding a stale claim token cannot commit | `test_permission_change_blocks_new_requests_immediately`, `test_running_job_rechecks_permission_before_commit` |
| FR-070/072/073 non-disclosure | No secret value appears in error envelopes or audit text | `tests/security/test_secret_non_disclosure.py` |
| FR-045/047/048/055 bridge | Bootstrap excludes sensitive dirs; incremental sync invalidates only affected modules; sync payload requires approved-root proof | `tests/unit/test_bridge_modules.py` |

Suite result: 11 relevant tests passed across acceptance/security/unit.

## Remaining risks

- The bridge scan/sync modules are bounded synthetic implementations; real
  workspace observation over an actual approved root and its Git state remains
  wired in the Release phase (bootstrap over the target host).
- Scenario D's full archive/asset secret safety and Scenario G's real index
  denial remain partially exercised; the FTS/semantic search layer is US5.
