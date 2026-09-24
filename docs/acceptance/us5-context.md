# US5 Scenario G/H evidence: bounded retrieval and context compiler

Date: 2026-09-23 Asia/Shanghai. Synthetic data only.

## Evidence

| Requirement | Observed outcome | Evidence source |
|---|---|---|
| FR-056 intent routing | Exact finance/todo intent classifies and routes to deterministic authority before semantic retrieval | `tests/acceptance/test_context_compiler.py::test_exact_finance_query_routes_before_semantic`, `tests/unit/test_context_tools.py` |
| FR-057 scope-before-search | Unauthorized scope denies before any candidate/index access (no search call) | `test_scope_before_search_denies_candidate_access`, `tests/acceptance/test_security_boundaries.py` |
| FR-060/ER-03 budget | compile_within_budget raises BUDGET_TOO_SMALL when mandatory warnings cannot fit; success packages always fit | `test_budget_enforced_and_warnings_preserved` |
| FR-067 permission-filtered retrieval | FTS/semantic candidate retrieval only returns authorized-scope entries | `packages/infrastructure/.../search/full_text.py`, `semantic.py` |
| FR-058/059/061..065 compiler | Context package deduplicates, prefers current-before-history and links sources/warnings | `packages/domain/.../retrieval/compiler.py`, `tests/unit/test_context_tools.py::test_context_package_preserves_warnings` |
| FR-099 tool surface | get_brain_context / search_brain / get_self_context exposed | `apps/server/.../context_tools.py` |
| Migration 0007 | Only ContextRequest/ContextPackage created; parent is 0006 assets search | `tests/migration/test_0007_retrieval_context.py` |

Suite result: 6 relevant tests passed across acceptance/unit/migration plus the
denial-before-search acceptance test.

## Remaining risks

- SC-011 budget metrics (all three detail levels with measured ceilings) are
  exercised only at unit level; capacity/Chinese-search benchmark (ER-12) is the
  Release-phase T162 workload.
- Semantic retrieval uses a deterministic synthetic score; real embeddings over
  pgvector and locked Chinese tokenization remain deployment-phase wiring.
