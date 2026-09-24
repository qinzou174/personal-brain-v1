# US2 Scenario B evidence: provenance and objective/subjective separation

Date: 2026-09-23 Asia/Shanghai. Synthetic data only.

## Evidence

| Requirement | Observed outcome | Evidence source |
|---|---|---|
| FR-007 reprocessing | Reprocessing the same raw text with the same generator yields a distinguishable new `derivation_id`; raw input id/text unchanged (never rewritten) | `tests/acceptance/test_provenance_and_experience.py::test_raw_text_remains_and_derivation_is_distinguishable` |
| FR-017 objective/subjective separation | Experience is created bound to its event and source with `establishment == "candidate"`; it is not a standalone global fact | `test_experience_separated_from_objective_event` |
| FR-030 provenance explanation | `explain_belief` reports source class label, generator version, evidence IDs and confidence basis | `test_provenance_explanation_reports_class_evidence_and_version` |
| FR-029/ER-01 orphan + versioning | Losing the last live source orphans derived content; each generation version is distinguishable | `tests/integration/test_lineage.py` (orphan, version replay, source authorization) |
| FR-065 derived access | Effective derived access is scope intersection with the maximum source sensitivity | `test_derived_access_requires_source_authorization` |

Suite result: `test_provenance_and_experience.py` + `test_lineage.py` = 6 passed
(1 shared-journey skip). Migration chain `0003_lineage_constraints` contract
test passes; round-trip against real PostgreSQL remains environment-gated like
0001/0002.

## Remaining risks

- SC-002 full-fixture (100%) sampling for every derived type is only partially
  evidenced here (lineage/reprocessing/provenance); the complete matrix remains a
  Release-phase acceptance.
- Real document/photo derivation across all supported formats stays in the US6
  asset phase; Scenario B's travel-photo link is not yet wired.
