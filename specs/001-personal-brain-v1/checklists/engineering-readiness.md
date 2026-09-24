# Engineering Readiness Checklist: Personal Brain V1

**Purpose**: Formal pre-implementation review of requirement precision, completeness,
consistency, traceability, safety, recovery, and execution readiness
**Created**: 2026-09-22
**Feature**: [spec.md](../spec.md)

**Note**: This checklist tests the requirements and planning artifacts, not implementation.
**Review Ownership**: Mark `[x]` only after a reviewer determines the requirement-quality
criterion is satisfied.
**Marker Semantics**: `[x]` means documentation quality is approved; it does not mean code or
delivery work is complete.

## Product Authority and Scope

- [ ] CHK001 Is the single-Brain authority defined consistently across intent, US1, FR-001, FR-002, plan boundaries, and client contracts? [Consistency, Spec §Product Intent, FR-001..FR-002]
- [ ] CHK002 Are V1 inclusions and exclusions precise enough to reject scope additions without relying on personal interpretation? [Clarity, Spec §In Scope/Out of Scope]
- [ ] CHK003 Is every future-reserved capability explicitly prevented from becoming a V1 mandatory dependency? [Coverage, SC-013, Plan §Delivery Phases]
- [ ] CHK004 Is the current documentation-only authorization boundary stated consistently in plan and tasks, with no wording that silently authorizes implementation? [Consistency, Plan §Authorization boundary, Tasks §Execution boundary]

## Canonical Truth and Provenance

- [ ] CHK005 Are canonical/derived and information-class requirements defined for every information-bearing entity rather than only documents? [Completeness, FR-005..FR-007, Data Model §Global Conventions]
- [ ] CHK006 Is “material derivation” bounded by enough criteria to decide which outputs require lineage and version history? [Clarity, FR-006, FR-086]
- [ ] CHK007 Are the effects of missing or deleted lineage on active derivations specified without allowing unsupported claims to remain silently active? [Edge Case, Data Model §DerivationEdge]
- [ ] CHK008 Are reprocessing and supersession requirements consistent between FR-007, R-004, DerivedContent states, and tasks.md US2 phase? [Consistency, Traceability]

## Structured Data and Exactness

- [ ] CHK009 Are exact-query domains and routing precedence explicitly defined so probabilistic retrieval cannot answer finance, todo, task state, permission, or lifecycle questions? [Clarity, FR-020, FR-056]
- [ ] CHK010 Are multi-currency, refund/adjustment, timezone, and relative-date requirements sufficiently specified for exact record behavior? [Coverage, Spec §Edge Cases, Data Model §Expense/Todo/Event]
- [ ] CHK011 Are terminal-state archive and corrective-history requirements consistent across Todo, Task, Memory, and deletion semantics? [Consistency, FR-015, FR-021, FR-049, FR-077..FR-080]

## Memory and Self-Model Safety

- [ ] CHK012 Are A/B/C classification boundaries explicit enough to distinguish an ordinary preference from an identity-level change? [Clarity, FR-023..FR-026]
- [ ] CHK013 Are promotion inputs measurable and explainable without implying that an opaque confidence number alone establishes truth? [Measurability, FR-025, R-010]
- [ ] CHK014 Are explicit-statement priority, contradiction, temporal change, contextual exceptions, and coexistence of traits mutually consistent? [Consistency, FR-027..FR-030]
- [ ] CHK015 Is user confirmation defined for every identity-level activation path, including reprocessing, import, and offline reconciliation? [Coverage, FR-026, FR-076, Gap]

## Security, Privacy, and Authorization

- [ ] CHK016 Is authorization-before-search specified at repository, index, cache, background-job, and source-reference boundaries? [Completeness, FR-067, FR-074, R-005]
- [ ] CHK017 Are denial responses constrained against existence, count, rank, timing, snippet, cache, and source-reference leakage? [Coverage, Tool Contracts §Common Error, Quickstart Scenario G]
- [ ] CHK018 Are credential rotation/overlap/revocation semantics and pending-work consequences unambiguous? [Clarity, FR-066, FR-069, FR-074]
- [ ] CHK019 Are secret exclusions complete across intake, assets, archives, project bootstrap, search, audit, logs, commits, and backups? [Coverage, FR-072, Operational Contracts §Secret Filter]
- [ ] CHK020 Are every high-risk operation's proposal version, expiry, impact, authorization, recovery, and audit requirements specified? [Completeness, FR-076, FR-079..FR-080, SC-015]
- [ ] CHK021 Is the public network boundary explicit enough to rule out exposing stores, workers, and administration surfaces? [Clarity, FR-075]

## Assets, Projects, and Local Boundaries

- [ ] CHK022 Are asset identity and byte deduplication requirements consistent with retaining distinct source/evidence relationships? [Consistency, FR-032..FR-033]
- [ ] CHK023 Are archive limits specified as configuration requirements for path, entry count, expansion size, nesting, type, and execution time? [Completeness, FR-038, Operational Contracts §Asset Intake]
- [ ] CHK024 Are image location fact/candidate rules and audio transcription derivation rules traceable to source authority? [Traceability, FR-035..FR-037]
- [ ] CHK025 Are current-source authority and ModuleCard navigation roles distinguished everywhere project context is described? [Consistency, FR-043..FR-048]
- [ ] CHK026 Are module freshness requirements adequate for commits, dirty files, partial module impact, non-Git workspaces, and unknown state? [Coverage, Spec §Edge Cases, R-011]
- [ ] CHK027 Are workspace containment requirements complete for normalized traversal, links/reparse points, absolute paths, alternate roots, and enumeration? [Coverage, FR-055, Operational Contracts §Workspace Bridge]
- [ ] CHK028 Is the non-guarantee for uncommitted source recovery visible in every cross-device/project-recovery expectation? [Consistency, FR-054, US4]

## Failure, Lifecycle, and Recovery

- [ ] CHK029 Are accepted, completed, pending-sync, unavailable, failed, conflict, and dead-letter outcomes defined without semantic overlap? [Clarity, Tool Contracts, FR-083..FR-088]
- [ ] CHK030 Are idempotency scope, payload mismatch, retention, and replay rules complete for client mutations, pending sync, and jobs? [Completeness, FR-011, R-007]
- [ ] CHK031 Does deletion impact cover originals, derivations, indexes, relations, evidence, caches, blobs, backups, confidence, and external cleanup? [Coverage, FR-079..FR-080]
- [ ] CHK032 Are retained-backup implications after deletion described clearly enough for owner consent and eventual expiry? [Clarity, Data Model §Deletion and Retention, tasks.md US8/US10 phases]
- [ ] CHK033 Are migration rollback-or-restore and post-validation requirements explicit for destructive and non-reversible changes? [Completeness, FR-085, Operational Contracts §Migration]
- [ ] CHK034 Is backup success consistently separated from isolated restore verification in requirements, model, operations contract, tests, and health? [Consistency, FR-094..FR-097, SC-010]

## Acceptance and Traceability

- [ ] CHK035 Does each V1 mandatory story define a standalone observable value and authoritative evidence, not merely a service or file artifact? [Acceptance Criteria, US1..US12]
- [ ] CHK036 Are the 16 success criteria objectively measurable without depending on undocumented implementation judgment? [Measurability, SC-001..SC-016]
- [ ] CHK037 Does every FR-001..FR-103 have at least one concrete task path and does every task cite a requirement, scenario, or governance gate? [Traceability, Tasks]
- [ ] CHK038 Do task dependencies prevent work from preceding Phase 0, foundation, migrations, authorization, or lineage prerequisites? [Consistency, Tasks §Dependencies]
- [ ] CHK039 Are test tasks ordered before implementation within each story and do they cover primary, alternate, error, recovery, security, and operational scenarios? [Coverage, Tasks, Quickstart]
- [ ] CHK040 Does the final gate require zero CRITICAL cross-artifact findings and an explicit owner implementation decision rather than inferred approval? [Governance, SC-016, final review and authorization tasks]

## Notes

- Focus: precision, full lifecycle coverage, authority boundaries, safety, recovery, and bidirectional traceability.
- Depth: formal pre-implementation gate.
- Reviewer/timing: owner or designated reviewer after tasks and cross-artifact analysis, before any implementation authorization.
- All items intentionally remain unchecked pending owner/designated-reviewer sign-off; the agent documentation assessment is in ../review-report.md; `$speckit-implement` must not change them.
