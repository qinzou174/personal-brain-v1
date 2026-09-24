# US3 Scenario C evidence: A/B/C self-model policy

Date: 2026-09-23 Asia/Shanghai. Synthetic data only.

## Evidence

| Requirement | Observed outcome | Evidence source |
|---|---|---|
| FR-023 class A | "记住，以后项目时间统一北京时间" -> policy_class A, active, establishment explicit | `tests/acceptance/test_self_model_policy.py::test_class_a_active_explicit_rule` |
| FR-024 class B candidate | "最近挺喜欢爵士乐" -> B, candidate, not established | `test_class_b_candidate_not_established` |
| FR-026 class C gate | "我的核心人生哲学已改变为 X" -> C, pending_confirmation, not active; imported/model text never counts as owner confirmation | `test_class_c_pending_confirmation_not_active`, `tests/unit/test_memory_policy.py::test_imported_or_model_text_never_counts_as_owner_confirmation` |
| FR-025 promotion thresholds | B promotion requires 3 sources / 14 days / 2 contexts / direct statement / no contradiction; same-source reprocessing counts once | `test_memory_policy.py` (`test_b_preference_established_at_all_inclusive_thresholds`, `test_reprocessing_one_canonical_source_does_not_multiply_evidence`) |
| FR-027 explicit outranks inference | Contradicting inference with an explicit statement supersedes it; prior stays historical | `tests/security/test_self_model_authority.py`, `tests/acceptance/test_self_model_policy.py::test_explicit_contradiction_supersedes_inference` |
| FR-029 evidence-removal | Removing one evidence triggers recalculation but preserves the claim history | `test_evidence_removal_recalculates_confidence_without_deleting_claim` |
| FR-022 retention | B candidate expires at 90 days; established becomes historical at 180; class A never ages into unconfirmed expiry | `test_memory_policy.py::test_b_candidate_and_established_age_boundaries`, `test_explicit_a_memory_does_not_age_into_unconfirmed_expiry` |
| FR-026/FR-076 confirmation | Class-C proposal approve/reject is version-bound, single-use and 15-minute expiring | `tests/unit/test_self_tools.py` |

Suite result: `test_self_model_policy.py` + `test_self_model_authority.py` +
`test_memory_policy.py` + `test_self_tools.py` = 31 passed.

## Remaining risks

- The confirmation flow is validated at the domain/application boundary with an
  in-memory store; SQL-backed proposals and review-inbox wiring are later tasks.
- SC-012 evidence matrix sampling here is synthetic; the full contradiction and
  deletion-evidence matrix belongs to US8 and the Release phase.
