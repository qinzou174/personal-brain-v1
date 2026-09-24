# Tasks: Personal Brain V1

**边界**：2026-09-23 用户已要求按 Skill 执行本清单；逐项状态以复选框和 `docs/acceptance/implementation-handoff.md` 为准。历史需求工程审查不代表产品已完成。

**输入**：spec、ER、plan、data-model、contracts、quickstart、source-coverage、traceability。编号是默认执行顺序；本版不标[P]，共享迁移/契约/索引默认串行。每阶段先写失败测试，再实施，再回归及记录权威证据。

## Phase 1: Setup / 授权与只读环境门禁

**门禁**：无实现授权时停在此处；未来必须先调查目标Linux主机。

- [X] T001 Record the owner's explicit implementation authorization, approved scope and excluded actions in `docs/acceptance/implementation-authorization.md`; documentation completion alone grants none [Constitution Gate 1, Current objective boundary]
- [X] T002 Produce the read-only target-host inventory in `docs/environment-report.md`, covering every field in `contracts/operational-contracts.md` and recording facts, unknowns, conflicts, and evidence [Constitution Phase 0]
- [X] T003 Record the owner-approved V1 deployment layout and port/path ownership decisions in `docs/deployment-decision.md` only after T002 evidence exists [Constitution Phase 0]
- [X] T004 Document exact-version official-source verification and compatibility evidence in `docs/dependency-baseline.md` before locking implementation dependencies [R-016]
- [X] T005 Initialize version control exclusions for secrets, personal data, database files, assets, backups, and environments in `.gitignore` [FR-072, FR-093]
- [X] T006 Create the future project package/workspace manifest and locked dependency policy in `pyproject.toml` without embedding credentials [R-016]
- [X] T007 Create server package boundaries in `apps/server/personal_brain_server/__init__.py` and `apps/server/personal_brain_server/bootstrap/` per `plan.md` [R-001]
- [X] T008 Create worker package boundaries in `apps/worker/personal_brain_worker/__init__.py` per `plan.md` [R-001]
- [X] T009 Create bridge package boundaries in `apps/bridge/personal_brain_bridge/__init__.py` per `plan.md` [FR-055, R-001]
- [X] T010 Create shared domain and infrastructure package boundaries in `packages/domain/personal_brain_domain/` and `packages/infrastructure/personal_brain_infra/` [R-001]
- [X] T011 Define safe configuration sources, required variables, validation, and secret redaction in `apps/server/personal_brain_server/bootstrap/settings.py` and `.env.example` [FR-070, FR-072]

## Phase 2: Foundation / 测试、安全与共享基础

**门禁**：所有US之前通过；仅用合成数据。

- [X] T012 Add migration round-trip and post-validation tests in `tests/migration/test_0001_authority_core.py` [FR-085]
- [X] T013 Add authorization-before-repository, revocation, error non-disclosure, and audit-body exclusion tests in `tests/security/test_authority_boundary.py` [FR-067..FR-076, SC-006]
- [X] T014 Add transaction/idempotency/job-crash property tests in `tests/integration/test_transactional_foundation.py` [FR-011, FR-083, FR-084, SC-008]
- [X] T015 Write failing remote OAuth discovery/PKCE/audience/revocation/origin and local stdio tests in `tests/contract/test_transport_auth.py` [FR-066..FR-075, FR-098, protocol-deployment.md]
- [X] T016 Write failing boundary tests in `tests/unit/test_validation_constraints.py`, `tests/unit/test_memory_policy.py`, `tests/unit/test_time_currency.py`; cover all model/ER required-nullable-enum-limit edges ±1 [FR-005, FR-012..FR-030, ER-01..ER-07]
- [X] T017 Create failing nine-journey harness/evidence schema in `tests/acceptance/conftest.py`, parameterized from traceability.md AC and SC IDs; final tasks execute rather than first create these tests [Constitution Gate 2, SC-001..SC-016]
- [X] T018 Define common canonical, derived, sensitivity, source-kind, validity, lifecycle, and concurrency value objects in `packages/domain/personal_brain_domain/common/types.py` [FR-005..FR-007, FR-071] Enforce `normal | personal | private | highly_private`, information classes, UUID IDs, title ≤512, query ≤8,000, text envelope ≤1 MiB, pagination 1..100 default20 and all data-model fields/enums.
- [X] T019 Define safe domain errors and stable contract error mapping in `packages/domain/personal_brain_domain/common/errors.py` [tool-contracts]
- [X] T020 Create the migration framework and ONLY Owner, Client, Credential, OAuthGrant, PermissionGrant, IntakeRequest, RawInput, AuditEvent, Idempotency, Job, DerivationEdge, DerivedContent and ReviewInboxItem in `migrations/versions/0001_authority_core.py`; later migrations reference, never recreate these tables. Enforce common constraints in data-model.md [FR-001..FR-011, FR-066..FR-074, FR-083, FR-085, ER-01, ER-06, ER-07]
- [X] T021 Implement transaction and unit-of-work boundary in `packages/infrastructure/personal_brain_infra/persistence/unit_of_work.py` so canonical state, jobs, idempotency outcome, and audit commit together [FR-011, FR-083, R-007]
- [X] T022 Implement client identity, opaque credential verification, rotation, and revocation domain logic in `packages/domain/personal_brain_domain/security/clients.py` [FR-066, FR-069, FR-070] Apply permission_epoch, rotation overlap ≤24h and ER-06 revocation checkpoints.
- [X] T023 Implement deny-first tool/scope/sensitivity policy evaluation in `packages/domain/personal_brain_domain/security/policy.py` [FR-067, FR-068, FR-071, FR-074..FR-076]
- [X] T024 Implement repository-enforced authorization predicates in `packages/infrastructure/personal_brain_infra/persistence/scoped_repository.py` so protected reads cannot run before policy resolution [FR-067, R-005]
- [X] T025 Implement idempotency claim/replay/conflict handling in `packages/infrastructure/personal_brain_infra/persistence/idempotency.py` [FR-011, R-007] Apply `(client_id, operation, idempotency_key)` uniqueness and ER-07 lifetime/tombstone rules.
- [X] T026 Implement body-free structured audit recording in `packages/domain/personal_brain_domain/security/audit.py` [FR-070, FR-073, FR-076]
- [X] T027 Implement secret-safe logging, correlation IDs, rotation settings, and redaction in `apps/server/personal_brain_server/bootstrap/logging.py` [FR-070, FR-072, FR-093]
- [X] T028 Implement durable job claim, lease, retry, dead-letter, and idempotent result semantics in `packages/infrastructure/personal_brain_infra/jobs/store.py` [FR-083, FR-084] Use lease60s, heartbeat20s, max5 attempts, 5/30/120/600s +20% jitter and fencing claim token [ER-07].
- [X] T029 Implement request/success/error envelopes plus `get_operation_status` lookup contract in `apps/server/personal_brain_server/protocols/contracts.py` [FR-087, FR-088, FR-098, tool-contracts]
- [X] T030 Implement canonical/derived classification and append-only derivation versioning in `packages/domain/personal_brain_domain/intake/lineage.py` [FR-005..FR-007]
- [X] T031 Implement source-trust and source-class policy in `packages/domain/personal_brain_domain/memory/source_policy.py` [FR-005, FR-006, FR-030]
- [X] T032 Implement filename/type/content secret detection and value-free results in `packages/domain/personal_brain_domain/security/secret_filter.py` [FR-072]
- [X] T033 Apply the secret filter before project, document, archive, log, and search persistence in `packages/domain/personal_brain_domain/intake/security_pipeline.py` [FR-045, FR-072]
- [X] T034 Implement normalized workspace-root containment including link/reparse resolution in `apps/bridge/personal_brain_bridge/workspace_boundary.py` [FR-055]
- [X] T035 Implement bounded Git revision/status/change/hash observation in `apps/bridge/personal_brain_bridge/git_observer.py` [FR-047, FR-048, FR-054, FR-055]
- [X] T036 Implement OAuth discovery, authorization-code+PKCE S256, exact redirects, audience/resource binding and revocation in `apps/server/personal_brain_server/security/oauth.py`; keep bounded static credentials separate [FR-066..FR-075, FR-098, ER-06]
- [X] T037 Implement owner-authenticated Inbox/proposal read/approve/reject/expiry in `apps/server/personal_brain_server/api/inbox.py`; version-bound confirmation15min/single-use [FR-010, FR-026, FR-076, ER-06]
- [X] T038 Define provider gateway and failing privacy tests in `packages/infrastructure/personal_brain_infra/models/gateway.py` and `tests/security/test_provider_boundary.py`; declare model/version/dimensions/tokenizer/sensitivity/budget, external disabled by default, timeout60s/max2 calls [FR-004, FR-006, FR-072, FR-084, FR-086, ER-12]
- [X] T039 Implement protocol adapters and authenticated `get_operation_status` registration for current official remote and local tool transports while exposing only authenticated Brain interfaces and no internal store/worker/admin surfaces in `apps/server/personal_brain_server/protocols/remote.py` and `apps/bridge/personal_brain_bridge/stdio.py` [FR-075, FR-098, FR-099]
- [X] T040 Implement minimal DB/job readiness/reconnect and repeatable synthetic fixtures in `apps/server/personal_brain_server/bootstrap/preflight.py` and `tests/conftest.py`; no real-data rollout before US10 restore gate [FR-083, FR-092]
- [X] T041 Create reproducible builds and entrypoints in `deploy/Dockerfile`, server/worker/bridge `__main__.py`; expose doctor preflight and named suites [FR-098, Source §48, §97]
- [X] T042 Create proposed `deploy/compose.yaml` with API/worker/PostgreSQL+pgvector, Trilium integration, internal DB/worker, volumes, healthchecks, log limits and tests in `tests/contract/test_deployment_boundary.py`; bind nothing before Phase0 approval [FR-075, FR-093, FR-100, Source §97..§102]
- [X] T043 Run foundation/protocol/secret/provider/transaction-crash tests and record `docs/acceptance/foundation.md`; skipped safety cases cannot pass [FR-001..FR-011, FR-066..FR-076, FR-083..FR-086]

## Phase 3: US1 / 一次记录，多端读取（P1，MVP）

**门禁**：Scenario A；双身份共享规范记录。

- [X] T044 [US1] Write failing intake and cross-client tool contract tests in `tests/contract/test_life_capture_contract.py` [FR-001..FR-020, SC-003, SC-008]
- [X] T045 [US1] Write failing mixed-statement end-to-end acceptance test in `tests/acceptance/test_cross_client_life_records.py` [US1, SC-001]
- [X] T046 [US1] Add exact aggregation, todo transition, concurrent replay, and source-link integration tests in `tests/integration/test_life_records.py` [FR-011..FR-020, SC-003, SC-008]
- [X] T047 [US1] Add Document, Expense, Todo, Event, Experience, Entity and Relation in `migrations/versions/0002_life_records.py`; RawInput/IntakeRequest already exist. Enforce `numeric(20,4)`, amount > 0, currency required, `pending | in_progress | completed | cancelled`, parent event acyclic, relation endpoints same owner [FR-012..FR-019, ER-04]
- [X] T048 [US1] Implement L0/L1/L2/L3 intake decision, low-value exclusion, and raw-first persistence in `packages/domain/personal_brain_domain/intake/service.py` [FR-003..FR-010, FR-008, FR-009] Class C overrides explicit remember; ambiguous currency/time routes to review; raw save does not depend on provider availability [ER-02, ER-04, ER-12].
- [X] T049 [US1] Implement exact Expense rules, currencies, adjustments, and aggregation in `packages/domain/personal_brain_domain/records/expenses.py` [FR-012, FR-013, FR-020]
- [X] T050 [US1] Implement Todo lifecycle, archive semantics, and deadline fields in `packages/domain/personal_brain_domain/records/todos.py` [FR-014, FR-015] Pending and in_progress may complete; terminal correction appends history [ER-04].
- [X] T051 [US1] Implement Event hierarchy, objective/subjective links, Entity types, and typed Relation primitives in `packages/domain/personal_brain_domain/records/timeline.py` [FR-016, FR-017, FR-018, FR-019]
- [X] T052 [US1] Implement mixed-statement extraction orchestration as derived work in `packages/domain/personal_brain_domain/intake/extraction.py` [FR-004..FR-007, FR-012..FR-019] Use foundation lineage; extracted interpretations never become original truth [ER-01, ER-02].
- [X] T053 [US1] Implement `save_note`, `add_expense`, `get_expense_summary`, `add_todo`, `list_todos`, and `complete_todo` application operations in `apps/server/personal_brain_server/api/life_tools.py` [FR-012..FR-020, FR-099]
- [X] T054 [US1] Register replaceable-client life-record operations through the protocol adapter in `apps/server/personal_brain_server/protocols/tools.py` without duplicating domain policy [FR-002, FR-098, FR-099]
- [X] T055 [US1] Record Scenario A evidence and remaining risks in `docs/acceptance/us1-cross-client-life-records.md` [US1, SC-001, SC-003, SC-008]

## Phase 4: US2 / 原始事实与可解释派生（P1）

**门禁**：Scenario B；重处理不改原件。

- [X] T056 [US2] Write failing lineage, reprocessing, and objective/subjective acceptance tests in `tests/acceptance/test_provenance_and_experience.py` [FR-004..FR-007, FR-017, SC-002]
- [X] T057 [US2] Add lineage orphan, source deletion, version replay, and source authorization integration tests in `tests/integration/test_lineage.py` [FR-006, FR-007, FR-029, FR-065]
- [X] T058 [US2] Add lineage target indexes, source-resolution constraints and Experience integration in `migrations/versions/0003_lineage_constraints.py`; reuse core DerivationEdge/DerivedContent and US1 Experience [FR-005..FR-007, FR-017, FR-086]
- [X] T059 [US2] Implement contextual Experience creation separated from objective Event facts in `packages/domain/personal_brain_domain/records/experiences.py` [FR-017]
- [X] T060 [US2] Implement reprocessing activation/supersession without canonical mutation in `packages/domain/personal_brain_domain/intake/reprocessing.py` [FR-007, FR-086]
- [X] T061 [US2] Implement provenance explanation queries in `packages/domain/personal_brain_domain/retrieval/provenance.py` [FR-030, FR-065]
- [X] T062 [US2] Record Scenario B and SC-002 sampling evidence in `docs/acceptance/us2-provenance.md` [US2, SC-002]

## Phase 5: US3 / Self Model治理（P1）

**门禁**：Scenario C；A/B/C、冲突与证据删除。

- [X] T063 [US3] Write failing A/B/C, contradiction, and evidence-removal acceptance tests in `tests/acceptance/test_self_model_policy.py` [FR-021..FR-030, SC-012]
- [X] T064 [US3] Add policy invariants ensuring inference cannot outrank explicit statements in `tests/security/test_self_model_authority.py` [FR-027, SC-012]
- [X] T065 [US3] Add Memory, SelfClaim, Evidence, Conflict, confidence-input, and confirmation mappings in `migrations/versions/0004_memory_self_model.py` [FR-021..FR-030, FR-077, FR-078] Reuse foundation ReviewInboxItem and versioned proposals.
- [X] T066 [US3] Implement memory lifecycle and policy-specific retention in `packages/domain/personal_brain_domain/memory/lifecycle.py` [FR-021, FR-022]
- [X] T067 [US3] Implement class A/B/C classification, candidate-first ordinary preferences, and confirmation gates in `packages/domain/personal_brain_domain/memory/self_model_policy.py` [FR-023..FR-028, FR-024] Keep lifecycle, establishment and review dimensions separate; cover import/reprocessing/offline class-C paths [ER-02, ER-06].
- [X] T068 [US3] Implement evidence contribution, confidence-input explanation, promotion, demotion, and recalculation in `packages/domain/personal_brain_domain/memory/evidence.py` [FR-025, FR-029, FR-030] Promotion needs ≥3 canonical inputs/14days/2contexts/1 direct statement/no contradiction; same-source reprocessing counts once [ER-02].
- [X] T069 [US3] Implement temporal validity, context, exceptions, contradiction, correction, and supersession in `packages/domain/personal_brain_domain/memory/history.py` [FR-027, FR-028, FR-077, FR-078]
- [X] T070 [US3] Implement confirmation proposal/approval/rejection operations in `apps/server/personal_brain_server/api/self_tools.py` [FR-026, FR-076]
- [X] T071 [US3] Record Scenario C and A/B/C evidence matrix in `docs/acceptance/us3-self-model.md` [US3, SC-012]

## Phase 6: US4 / Project Brain连续性（P1）

**门禁**：Scenario E；未知不得伪装fresh。

- [X] T072 [US4] Write failing project-task recovery and freshness acceptance tests in `tests/acceptance/test_project_recovery.py` [FR-041..FR-054, SC-004, SC-005]
- [X] T073 [US4] Add source-authority and stale-warning integration tests in `tests/integration/test_project_authority.py` [FR-044, FR-048, SC-005]
- [X] T074 [US4] Add Project, ModuleCard, ProjectTask, Checkpoint, Decision, Constraint, ChangeEvent, and Milestone mappings in `migrations/versions/0005_project_brain.py` [FR-041..FR-053] Include WorkspaceObservation and exact Task/Module freshness enums from data-model.md.
- [X] T075 [US4] Implement Project/Profile invariants in `packages/domain/personal_brain_domain/projects/projects.py` [FR-041, FR-042]
- [X] T076 [US4] Implement ModuleCard fields and fresh/stale/unknown transitions in `packages/domain/personal_brain_domain/projects/modules.py` [FR-043, FR-044, FR-048] Use foundational Git/hash observer and relevant-file CAS; racing refresh remains stale/unknown [ER-08].
- [X] T077 [US4] Implement Task start lifecycle with revision/dirty/constraint evidence in `packages/domain/personal_brain_domain/projects/tasks.py` [FR-049, FR-050]
- [X] T078 [US4] Implement append-only checkpoint capture in `packages/domain/personal_brain_domain/projects/checkpoints.py` [FR-051]
- [X] T079 [US4] Implement finalize comparison, report, change-event, and decision deduplication in `packages/domain/personal_brain_domain/projects/finalize.py` [FR-052]
- [X] T080 [US4] Implement legacy project-document extraction with preserved sources/confidence in `packages/domain/personal_brain_domain/projects/bootstrap_docs.py` [FR-046]
- [X] T081 [US4] Implement project/task/module/recent-change read and write operations in `apps/server/personal_brain_server/api/project_tools.py` [FR-041..FR-053, FR-099]
- [X] T082 [US4] Implement fresh-client recovery package assembly in `packages/domain/personal_brain_domain/projects/recovery.py` [FR-053, FR-054]
- [X] T083 [US4] Record no-chat-history recovery timing and completeness in `docs/acceptance/us4-project-recovery.md` [US4, SC-004, SC-005]

## Phase 7: US7 / 工作区安全与增量Bridge（P2，US5前置）

**门禁**：Scenarios F/G/D；根目录、密钥与增量边界。

- [X] T084 [US7] Write failing secret-filter corpus, workspace-escape, denial-before-search, and revocation acceptance tests in `tests/acceptance/test_security_boundaries.py` [FR-045, FR-055, FR-066..FR-076, SC-006, SC-007]
- [X] T085 [US7] Add concurrent permission-change and already-running-job safety tests in `tests/security/test_permission_races.py` [FR-074]
- [X] T086 [US7] Add a no-secret-in-log/search/audit regression suite in `tests/security/test_secret_non_disclosure.py` [FR-070, FR-072, FR-073, SC-007]
- [X] T087 [US7] Implement bootstrap exclusion rules and no-full-disk enumeration in `apps/bridge/personal_brain_bridge/bootstrap_scan.py` [FR-045, FR-055] Produce Profile, Module Map/Cards, dependencies, API, DB, config, constraints, TODO and risks [ER-08, Source §36].
- [X] T088 [US7] Implement incremental changed-file mapping and affected-module invalidation in `apps/bridge/personal_brain_bridge/incremental_sync.py` [FR-047, FR-048]
- [X] T089 [US7] Implement bridge-to-Brain sync contract and approved-root proof in `apps/bridge/personal_brain_bridge/client.py` [FR-047, FR-055, FR-098]
- [X] T090 [US7] Record denied scopes, revoked client, boundary escapes, and secret corpus evidence in `docs/acceptance/us7-security.md` [US7, SC-006, SC-007]

## Phase 8: US6 / 资产与重处理（P2，US5前置）

**门禁**：Scenario D；原件、归档、恢复边界。

- [X] T091 [US6] Write failing asset identity, dedupe, integrity, archive-limit, and reprocessing acceptance tests in `tests/acceptance/test_assets.py` [FR-031..FR-040, SC-002, SC-009]
- [X] T092 [US6] Add ONLY Asset, AssetBlob and SearchIndexEntry in `migrations/versions/0006_assets_search.py`; reuse core DerivedContent. Enforce unique `(sha256, size)` and all data-model enums [FR-031..FR-040, FR-086]
- [X] T093 [US6] Define StorageBackend and content-addressed atomic promotion contract in `packages/infrastructure/personal_brain_infra/storage/base.py` [FR-032, FR-033, FR-040]
- [X] T094 [US6] Implement local filesystem backend with hash/size verification and no caller-selected path in `packages/infrastructure/personal_brain_infra/storage/local.py` [FR-032, FR-033, FR-039, FR-040]
- [X] T095 [US6] Implement streaming asset intake and duplicate-blob/source-link behavior in `packages/domain/personal_brain_domain/assets/intake.py` [FR-031..FR-033] Apply ≤100MiB upload, ≤255 name and quarantine gate before canonical promotion [ER-05].
- [X] T096 [US6] Implement bounded document processing and original-preserving image metadata, capture-time/location evidence, annotations, tags, and descriptions in `packages/domain/personal_brain_domain/assets/document_processors.py` [FR-034..FR-036, FR-035]
- [X] T097 [US6] Implement bounded audio metadata and optional transcription processor in `packages/domain/personal_brain_domain/assets/audio_processor.py` [FR-037]
- [X] T098 [US6] Implement safe archive listing/extraction limits and traversal rejection in `packages/domain/personal_brain_domain/assets/archive_processor.py` [FR-038] Enforce ER-05 archive limits: 1,000 entries, listing30s/1MiB, name512, extraction500MiB/100MiB each/100:1/60s/nesting0; deny links/encryption/traversal.
- [X] T099 [US6] Implement asset integrity scan and dependent impact reporting in `packages/domain/personal_brain_domain/assets/integrity.py` [FR-039]
- [X] T100 [US6] Implement versioned parse/embed/reprocess job handlers in `apps/worker/personal_brain_worker/asset_jobs.py` [FR-034..FR-038, FR-086]
- [X] T101 [US6] Implement streamed `upload_asset` operation in `apps/server/personal_brain_server/api/asset_tools.py` [FR-031..FR-040, FR-099]
- [X] T102 [US6] Record supported-class byte identity, dedupe, archive safety, and reprocessing evidence in `docs/acceptance/us6-assets.md` [US6, SC-002, SC-009]

## Phase 9: US5 / 有界检索与上下文（P1，按依赖后置）

**门禁**：Scenarios G/H；权限先检索与预算。

- [X] T103 [US5] Write failing intent-routing, scope-before-search, and budget acceptance tests in `tests/acceptance/test_context_compiler.py` [FR-056..FR-065, SC-003, SC-006, SC-011]
- [X] T104 [US5] Add ONLY ContextRequest and ContextPackage in `migrations/versions/0007_retrieval_context.py`; reuse SearchIndexEntry from US6. Parent revision is 0006_assets_search [FR-056..FR-065]
- [X] T105 [US5] Implement intent classification and deterministic structured dispatch in `packages/domain/personal_brain_domain/retrieval/router.py` [FR-020, FR-056]
- [X] T106 [US5] Implement permission-filtered full-text candidate retrieval in `packages/infrastructure/personal_brain_infra/search/full_text.py` [FR-057, FR-067] Use locked Chinese tokenization and permission-filtered lexical fallback [protocol-deployment.md, ER-12].
- [X] T107 [US5] Implement permission-filtered semantic candidate retrieval and versioned embeddings in `packages/infrastructure/personal_brain_infra/search/semantic.py` [FR-057, FR-065, FR-086]
- [X] T108 [US5] Implement rank normalization across relevance, keyword, recency, confidence, trust, importance, validity, freshness, and scope in `packages/domain/personal_brain_domain/retrieval/ranking.py` [FR-057] Apply hard filters, current-source priority, RRF k=60 and deterministic tie-break reasons [ER-03].
- [X] T109 [US5] Implement hierarchical selection, deduplication, current-before-history authority, historical-rationale linking, uncertainty warnings, and source links in `packages/domain/personal_brain_domain/retrieval/compiler.py` [FR-058, FR-059, FR-061..FR-065, FR-062, FR-063, FR-064]
- [X] T110 [US5] Implement summary/normal/deep budget enforcement that preserves critical warnings in `packages/domain/personal_brain_domain/retrieval/budget.py` [FR-060, SC-011] Enforce 2,000/6,000/12,000 ceilings including metadata; return BUDGET_TOO_SMALL when mandatory warnings cannot fit [ER-03].
- [X] T111 [US5] Expose scoped `get_brain_context`, `search_brain`, and `get_self_context` operations in `apps/server/personal_brain_server/api/context_tools.py` [FR-056..FR-065, FR-099]
- [X] T112 [US5] Record router authority, denial-before-search, and budget metrics in `docs/acceptance/us5-context.md` [US5, SC-003, SC-006, SC-011]

## Phase 10: US8 / 冲突、保留和删除（P2）

**门禁**：Scenario J；预览无副作用，确认后执行。

- [X] T113 [US8] Write failing conflict, retention, evidence-deletion, and deletion-plan acceptance tests in `tests/acceptance/test_lifecycle_deletion.py` [FR-021, FR-029, FR-077..FR-082, SC-015]
- [X] T114 [US8] Add backup-retention disclosure and post-delete non-disclosure tests in `tests/security/test_deletion_privacy.py` [FR-079, FR-080]
- [X] T115 [US8] Add ONLY DeletionPlan, DeletionAction and retention mappings in `migrations/versions/0008_lifecycle_deletion.py`; reuse ReviewInboxItem/Conflict and add value-free deletion ledger [FR-077..FR-082, ER-09]
- [X] T116 [US8] Implement conflict detection and time/user/tolerated resolution without participant loss in `packages/domain/personal_brain_domain/memory/conflicts.py` [FR-077, FR-078]
- [X] T117 [US8] Implement type-specific retention, archive, expiry, promotion, and demotion orchestration in `packages/domain/personal_brain_domain/operations/retention.py` [FR-021, FR-022, FR-081, FR-082]
- [X] T118 [US8] Implement deletion dependency graph and action classification in `packages/domain/personal_brain_domain/operations/deletion_plan.py` [FR-079] No hide/purge before confirmation; preview shared blobs and backup remnants [ER-09].
- [X] T119 [US8] Implement versioned confirmation and governed delete/detach/tombstone/recompute execution in `packages/domain/personal_brain_domain/operations/deletion.py` [FR-029, FR-076, FR-079, FR-080] Reject stale proposals; separate production_purged from backup_purge_due; restore replays deletion ledger [ER-06, ER-09].
- [X] T120 [US8] Implement search/cache/asset cleanup reconciliation jobs in `apps/worker/personal_brain_worker/deletion_jobs.py` [FR-079, FR-080, FR-084]
- [X] T121 [US8] Implement review inbox operations for conflict, merge, profile, deletion, and failed reconciliation in `apps/server/personal_brain_server/api/review_tools.py` [FR-010, FR-026, FR-077..FR-080]
- [X] T122 [US8] Record complete dependency handling and evidence recalculation in `docs/acceptance/us8-lifecycle.md` [US8, SC-015]

## Phase 11: US9 / 断网与重放（P2）

**门禁**：Scenario I；诚实状态、一次结果。

- [X] T123 [US9] Write failing offline acknowledgement, replay, and conflict acceptance tests in `tests/acceptance/test_offline_reconciliation.py` [FR-087, FR-088, SC-008]
- [X] T124 [US9] Add revoked-client-with-pending-writes and crash-after-commit tests in `tests/integration/test_reconciliation_edges.py` [FR-074, FR-084, FR-088]
- [X] T125 [US9] Define bridge/client pending operation store and states in `apps/bridge/personal_brain_bridge/pending_store.py` [FR-087, FR-088] Opt-in queue ≤1,000 ops/100MiB, prefilter secrets, OS ACL + protected local key; revoke stops replay [ER-07].
- [X] T126 [US9] Implement unavailable/failed/pending-sync outcome mapping without false success in `apps/bridge/personal_brain_bridge/offline.py` [FR-084, FR-087]
- [X] T127 [US9] Implement ordered idempotent retry and authoritative-outcome reconciliation in `apps/bridge/personal_brain_bridge/reconcile.py` [FR-011, FR-088]
- [X] T128 [US9] Implement conflict-to-review handoff preserving both versions in `packages/domain/personal_brain_domain/intake/reconciliation.py` [FR-010, FR-077, FR-088]
- [X] T129 [US9] Record offline status wording, one-outcome replay, and conflict evidence in `docs/acceptance/us9-offline.md` [US9, SC-008]

## Phase 12: US12 / 人类笔记界面（P3但V1必需）

**门禁**：Scenario N；Trilium集成必需、可移除。

- [X] T130 [US12] Write failing source-preserving import and no-dependency acceptance tests in `tests/acceptance/test_human_knowledge_interface.py` [FR-100..FR-102]
- [X] T131 [US12] Add ExternalSource and ImportCheckpoint mappings in `migrations/versions/0009_external_sources.py` and define bounded source identity/conflict/checkpoint contract in `packages/domain/personal_brain_domain/intake/human_knowledge_contract.py` [FR-100, FR-101]
- [X] T132 [US12] Verify Trilium deployment/connection in `docs/TRILIUM_SETUP.md` and `tests/integration/test_trilium_import.py`; one-way paged idempotent import, source revision/checkpoint/conflict/secret/backup, no core-health dependency [FR-100, FR-101, Source §71, §127]
- [X] T133 [US12] Implement reliable one-way import through ordinary intake/lineage policy in `apps/worker/personal_brain_worker/human_knowledge_import.py` [FR-004..FR-007, FR-100, FR-101]
- [X] T134 [US12] Implement optional source health and last-import status without core readiness dependency in `packages/domain/personal_brain_domain/operations/external_source_health.py` [FR-100]
- [X] T135 [US12] Define source-linked derived digest navigation in `packages/domain/personal_brain_domain/retrieval/digests.py`; automatic daily/weekly/monthly generation is OPTIONAL and cannot gate V1 [FR-102]
- [X] T136 [US12] Record import provenance and core behavior with the interface disabled in `docs/acceptance/us12-human-interface.md` [US12]

## Phase 13: US10 / 运维、备份与恢复（P2）

**门禁**：Scenarios K/L；真实数据上线硬门禁。

- [X] T137 [US10] Write failing durable-job crash/dead-letter and aggregate-health acceptance tests in `tests/acceptance/test_operational_health.py` [FR-081..FR-086, FR-092, FR-093]
- [X] T138 [US10] Write failing backup inventory and isolated restore acceptance test in `tests/restore/test_full_restore.py` [FR-094..FR-097, SC-009, SC-010]
- [X] T139 [US10] Add corrupted asset, broken relation, low disk, overdue backup, and failed restore tests in `tests/integration/test_doctor_findings.py` [FR-039, FR-092, FR-093]
- [X] T140 [US10] Add backup tier expiration and deleted-data disclosure tests in `tests/restore/test_backup_retention.py` [FR-079, FR-096]
- [X] T141 [US10] Add BackupSet, RestoreVerification, HealthFinding, migration-evidence, and integrity-history mappings in `migrations/versions/0010_operations.py` [FR-085, FR-092..FR-097]
- [X] T142 [US10] Implement deterministic doctor checks for database, assets, relations, indexes, stale modules, inbox, jobs, backups, restore age, and capacity in `packages/domain/personal_brain_domain/operations/doctor.py` [FR-081, FR-082, FR-092]
- [X] T143 [US10] Implement bounded retention for logs, temporary data, notifications, and rebuildable indexes in `packages/domain/personal_brain_domain/operations/growth.py` [FR-093]
- [X] T144 [US10] Implement canonical backup inventory, database-consistent export, asset manifest, hashes, and tier metadata in `deploy/scripts/backup.sh` and `packages/domain/personal_brain_domain/operations/backup.py` [FR-094, FR-096, FR-097] Freeze DB+asset cutoff; include Trilium/Git/config/deletion ledger; use 7daily/4weekly/3monthly subject to ER-10 floor.
- [X] T145 [US10] Implement isolated restore orchestration and verification record generation in `deploy/scripts/verify-restore.sh` and `packages/domain/personal_brain_domain/operations/restore.py` [FR-095, FR-097] Verify fixture100%; production samples/permissions/assets per ER-10; RPO24h/RTO4h remain proposed until measured.
- [X] T146 [US10] Implement schema-migration preflight, backup gate, post-validation, and health evidence in `deploy/scripts/migrate.sh` [FR-085]
- [X] T147 [US10] Implement health API/tool response without collapsing component failures into HTTP availability in `apps/server/personal_brain_server/api/health.py` [FR-092]
- [X] T148 [US10] Implement deterministic maintenance and reprocessing job handlers in `apps/worker/personal_brain_worker/maintenance_jobs.py` [FR-081..FR-086]
- [X] T149 [US10] Implement owner-authorized portable export/import with schema/source/blob manifest in `packages/domain/personal_brain_domain/operations/export.py` and `tests/restore/test_portable_export.py`; exclude credentials/caches [Constitution I, FR-040, FR-076, FR-094]
- [X] T150 [US10] Define `deploy/maintenance-schedule.yaml` and `docs/acceptance/operations-schedule.md`; daily backup, first/after-migration/monthly restore, single scheduler, disk15%warn/5%critical [FR-081..FR-085, FR-092..FR-097, ER-10, ER-11]
- [X] T151 [US10] Record isolated restore results, sampled hashes, permission invariants, and independent timestamps in `docs/acceptance/us10-restore.md` [US10, SC-009, SC-010]

## Phase 14: US11 / 克制通知（P3但V1必需）

**门禁**：Scenario M；Inbox必需，外部渠道可选。

- [X] T152 [US11] Write failing trigger/cooldown/merge/non-trigger acceptance tests in `tests/acceptance/test_notifications.py` [FR-089..FR-091]
- [X] T153 [US11] Add Notification trigger, candidate, suppression, delivery, and acknowledgement mappings in `migrations/versions/0011_notifications.py` [FR-089..FR-091]
- [X] T154 [US11] Implement V1 trigger registry and detect-notify separation in `packages/domain/personal_brain_domain/operations/notification_triggers.py` [FR-089, FR-090]
- [X] T155 [US11] Implement priority, cooldown, merge, dedupe, preference, and channel policy in `packages/domain/personal_brain_domain/operations/notification_policy.py` [FR-091] Use 10min merge, 60min cooldown, daily persistent recap; date-only 09:00 scheduling does not invent due time [ER-11].
- [X] T156 [US11] Implement notification dispatch job with safe failure visibility in `apps/worker/personal_brain_worker/notification_jobs.py` [FR-084, FR-091] Provide mandatory owner Inbox acknowledgement; external channels are optional and preauthorized [ER-06, ER-11].
- [X] T157 [US11] Record enabled triggers, suppression evidence, and no-notify trend case in `docs/acceptance/us11-proactivity.md` [US11]

## Phase 15: Release / 跨端、文档与最终验收

**门禁**：真实客户端与所有12故事，mock不能替代。

- [X] T158 Publish client behavior rules in `docs/PERSONAL_BRAIN_RULES.md` covering memory policy, task checkpoints, freshness, source authority, inference, and structured queries [FR-103]
- [X] T159 Publish architecture and data authority documentation in `docs/ARCHITECTURE.md` and `docs/DATA_MODEL.md` [FR-001..FR-103]
- [X] T160 Publish `README.md`, `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`, `docs/MCP_TOOLS.md`, `docs/SECURITY.md`, `docs/DEPLOYMENT.md`, `docs/BACKUP_RESTORE.md`, `docs/TRAE_SETUP.md`, `docs/CURSOR_SETUP.md`, `docs/BRIDGE_SETUP.md`, `docs/PERSONAL_BRAIN_RULES.md`, `docs/PROJECT_BRAIN_RULES.md`, and `docs/OPERATIONS.md` [FR-066..FR-103, Source §136]
- [X] T161 Publish backup/restore procedures and evidence interpretation in `docs/BACKUP_RESTORE.md` [FR-094..FR-097]
- [X] T162 Create ER-12 benchmark and Chinese retrieval fixtures in `tests/acceptance/test_capacity_and_chinese_search.py`; 10k records/1k docs/100 modules/5 concurrent, 1,000 cold+warm, p95 300ms/2s/1s, errors≤1%, record hardware [FR-034, FR-057, FR-060, FR-092, ER-12]
- [X] T163 Run actual TRAE/Cursor/ChatGPT connection, cross-client read/write, revocation and no-history resume in `tests/acceptance/test_real_clients.py` and `docs/acceptance/client-matrix.md`; mocks are not substitutes and blocked results stay EXTERNAL_VERIFICATION_PENDING [FR-002, FR-053, FR-069, FR-098, SC-001, SC-004]
- [X] T164 Validate all nine source-defined V1 success journeys in `tests/acceptance/test_source_v1_scenarios.py` and link outputs from `docs/acceptance/v1-evidence-index.md` [SC-001]
- [X] T165 Validate context recovery under removed chat history and replaced client identity in `tests/acceptance/test_context_loss_recovery.py` [FR-053, SC-004]
- [X] T166 Validate out-of-scope components are absent from core dependency and deployment graphs in `tests/contract/test_v1_scope.py` [SC-013]
- [X] T167 Validate every high-risk workflow has target, impact preview, authorization, recovery, and audit evidence in `tests/security/test_high_risk_gate.py` [FR-076, FR-079, SC-015]
- [X] T168 Run and preserve all quickstart scenario evidence in `docs/acceptance/v1-evidence-index.md`, explicitly separating command success from behavioral acceptance [SC-001..SC-016]
- [X] T169 Generate and review final requirement-to-task and task-to-requirement coverage in `docs/acceptance/traceability-matrix.md` [SC-014, SC-016]
- [X] T170 Run final cross-artifact and constitution review and record zero unresolved CRITICAL findings in `docs/acceptance/final-readiness-review.md` [SC-016]

## 依赖与交付策略

授权 → 真实环境只读调查 → Foundation → US1 → US2 → US3 → US4 → US7 → US6 → US5 → US8 → US9 → US12 → US10 → US11 → Release。P1/P2/P3是价值优先级，不能覆盖数据和安全依赖；US11/US12仍是V1范围。

迁移链：0001_authority_core → 0002_life_records → 0003_lineage_constraints → 0004_memory_self_model → 0005_project_brain → 0006_assets_search → 0007_retrieval_context → 0008_lifecycle_deletion → 0009_external_sources → 0010_operations → 0011_notifications。文件号不是自动排序依据，以parent revision为准；实体只创建一次。空库可初始化；已有数据迁移必须先有已验证恢复点，US10前只操作可丢弃合成库。

每阶段：失败用例 → 实施 → 本阶段和受影响回归 → GWT/输入/权威结果/失败风险 → 下阶段。表字段、可空性、枚举和ER全文是每个消费实体任务的必读输入。

**Phase 15 基线统计**：T001-T170 共170项，170项执行完成。此处测试数字仅为当时基线；当前权威统计见文末 Phase 17 与 `docs/acceptance/final-readiness-review.md`。外部不可访问时保留 EXTERNAL_VERIFICATION_PENDING，不能勾选完成。

## Phase 16: Convergence

**门禁**：本阶段修复实现与既定目标之间的偏移。旧任务勾选和既有 PASS 文档不是完成证据；每项必须以真实运行路径、权威持久化结果或明确的外部门禁状态验收。

- [X] T171 **CRITICAL** Replace process-local canonical stores with owner-scoped PostgreSQL repositories and wire intake, life records, projects, self model, review inbox, operation status, audit, idempotency and jobs through one UnitOfWork so `canonical_committed` is returned only after the authoritative transaction commits; add restart and two-process visibility tests per Constitution I, FR-001..FR-011, FR-012..FR-030, FR-041..FR-053, FR-083 (contradicts)
- [X] T172 **CRITICAL** Implement real long-running server, worker and bridge entrypoints with configuration preflight, graceful shutdown, health/readiness, durable worker polling and stdio protocol lifecycle; make the Docker image install/run the project environment and make Compose mount every required secret and data path per plan: runtime/deployment, T041, T042, FR-075, FR-083, FR-092, FR-098 (missing)
- [X] T173 **CRITICAL** Derive client identity and permission grants exclusively from verified credentials/OAuth and persisted authority state, remove caller-supplied grants from protected application boundaries, apply permission_epoch checks before source read, external call, canonical commit and response, and add revocation-race tests per Constitution IV, FR-066..FR-076, ER-06 (contradicts)
- [X] T174 **CRITICAL** Complete local stdio and remote HTTPS Streamable-HTTP MCP adapters with discovery, initialize, tools/list, tools/call, stable envelopes, operation-status lookup, session handling and the full FR-099 tool surface for context, search, notes, self, finance, todos, projects/modules/tasks, workspace sync/freshness and assets per FR-098, FR-099, T039 (partial)
- [X] T175 **CRITICAL** Replace hard-coded synthetic journey approvals with end-to-end acceptance that starts the real API/worker/bridge against an isolated PostgreSQL and asset store, performs each of J01..J09, captures machine-verifiable outputs, and rejects evidence references not produced by the current run per Constitution VI, SC-001..SC-012, T164, T168 (contradicts)
- [X] T176 **CRITICAL** Implement honest isolated restore orchestration and verification using expected-versus-restored canonical counts, relationships, client permissions, deterministic queries, deletion ledger and asset hashes; remove constant 100-percent and unconditional success paths and record independent backup/restore timestamps per Constitution V, FR-095, FR-097, SC-009, SC-010, T145, T151 (contradicts)
- [X] T177 Persist original assets atomically through the configured StorageBackend, persist Asset/Blob/source/integrity metadata and derivation jobs transactionally, wire parse/transcribe/describe/embed handlers to real bytes and versions, and prove byte-identical dedupe/reprocess/restore behavior per FR-031..FR-040, SC-009 (partial)
- [X] T178 Implement durable Project Brain bootstrap and incremental synchronization from the approved workspace root, including exclusions, current Git evidence, module freshness invalidation, task/checkpoint/finalization persistence and fresh-client recovery without process-local stores per FR-041..FR-055, SC-004, SC-005 (partial)
- [X] T179 Replace dictionary and character-overlap retrieval with owner/scope predicates pushed into PostgreSQL FTS and pgvector queries, locked Chinese tokenization, versioned embeddings, deterministic exact-route bypass, RRF ranking, provenance/source links and visible stale/conflict/uncertainty warnings per FR-020, FR-056..FR-065, FR-067, ER-03 (partial)
- [X] T180 Persist confirmation, conflict, retention and deletion workflows; require owner-bound single-use versioned authorization, execute the dependency plan across originals/derived/indexes/relations/evidence/caches, enqueue fenced reconciliation, recalculate evidence and record body-free audit outcomes per FR-021..FR-030, FR-076..FR-080, SC-015 (contradicts)
- [X] T181 Implement the encrypted, ACL-protected, size-bounded offline queue and ordered replay; connect durable job handlers for asset, deletion, maintenance, reprocessing and notification work to the job store with heartbeat, fencing, retry/dead-letter, progress and permission/secret/version rechecks per FR-083, FR-084, FR-087..FR-093, ER-07, ER-11 (partial)
- [X] T182 Harden OAuth and provider execution: registered exact redirect URIs, authorization-code/token expiry, persisted grants and permission epochs, token revocation, bounded provider call counting, enforced timeout, declared context/sensitivity budgets and value-free failure/audit behavior per FR-004, FR-006, FR-066..FR-075, FR-084, FR-086, ER-06, ER-12 (partial)
- [X] T183 Produce a database-consistent, encrypted backup set with coordinated DB/asset cutoff, complete authoritative-source/config/schema/deletion-ledger manifests, hash verification, independently controlled key handling and capacity-safe 7-daily/4-weekly/3-monthly retention; fail closed instead of suppressing missing inputs per FR-094, FR-096, FR-097, ER-10 (partial)
- [X] T184 Run the complete 0001..0011 migration chain against an isolated `*_test` PostgreSQL/pgvector database, validate all constraints/indexes/data transitions and health evidence, exercise safe rollback/restore protection, and make an unavailable DSN an explicit skip while retaining at least one authoritative real-PostgreSQL result per FR-085, T012, T020, T146 (partial)
- [X] T185 Build and run the ER-12 benchmark at 10k structured records, 1k documents, 100 modules and 5 concurrent clients for 1,000 cold and warm queries; record hardware, dataset seed, p50/p95, error rate, budget/warning preservation and Chinese retrieval quality against the 300ms/2s/1s and <=1% gates per FR-034, FR-057, FR-060, FR-092, ER-12, T162 (missing)
- [ ] T186 Execute the externally gated Trilium, TRAE CN, Cursor and ChatGPT integrations through the reachable authenticated deployment, capturing versions, discovery/login, scoped read/write, cross-client/no-history recovery, revocation and failure evidence; keep this task unchecked as EXTERNAL_VERIFICATION_PENDING until every real-client row has authoritative evidence per FR-002, FR-053, FR-069, FR-098, FR-100, FR-101, T132, T163 (missing)
- [X] T187 Re-run full functional, security, migration, restore, capacity and real-client acceptance after T171..T186; reconcile task counts and PASS/PENDING states across tasks.md and every acceptance document, remove contradictory statistics, generate bidirectional requirement/task/evidence coverage, and record zero unresolved CRITICAL findings only when the constitution gates actually pass per Constitution VI, SC-014, SC-016, T168..T170 (contradicts)

## Phase 17: Convergence

- [X] T188 **CRITICAL** Separate the container listen address from the owner-approved host publish address so the API listens on a valid container interface while Compose publishes only `192.168.10.7:18081`; prove the production-shaped API starts, remains LAN-only and exposes no DB/worker/admin port per FR-075, T172, plan: runtime/deployment (contradicts)
- [X] T189 **CRITICAL** Declare and mount the PostgreSQL password secret referenced by `POSTGRES_PASSWORD_FILE`, validate all API/worker/DB secret mounts without embedding values, and add a real Compose startup/failure/cleanup acceptance path per FR-070, FR-075, T172, plan: runtime/deployment (missing)
- [X] T190 Implement an owner-controlled bootstrap and client lifecycle operator flow for first-owner creation, least-privilege client provisioning, one-time credential delivery to an ACL-protected file, rotation and revocation; never print or persist reusable credentials in logs or ordinary Brain data per Constitution IV, FR-066..FR-070 (missing)
- [X] T191 Implement owner-authorized post-creation project-scope grant management so a client allowed to create a project can receive, inspect and revoke the exact `project:<id>` read/write grants needed for subsequent task, checkpoint, sync and recovery calls; verify denial before grant and fresh-client recovery after grant per FR-041..FR-053, FR-067, FR-068 (partial)
- [X] T192 Re-run local, isolated PostgreSQL/pgvector, production-shaped Compose, API/worker/bridge and client lifecycle acceptance after T188..T191; reconcile README, handoff, readiness review, traceability and task counts, and restore the zero-unresolved-CRITICAL claim only from current behavioral evidence per Constitution VI, SC-014, SC-016, T187 (contradicts)

## Phase 18: Windows local trial and model activation

- [X] T193 Install and run a separate Windows-local PostgreSQL 16/pgvector instance, migrate it, and run the full regression suite against an isolated `brain_test` database; preserve the LAN Brain as a separate data set.
- [X] T194 Recover expired worker leases with fencing and fix Chinese phrase search against real indexed notes; verify the original display excerpt through the live MCP route.
- [X] T195 Start the Windows API and worker on loopback, provision a separate client, add `personal-brain-local` to TRAE CN, and verify the actual stdio bridge plus save/search behavior.
- [X] T196 Provide and run Windows start/stop scripts, verify stop and restart persistence, and publish a user-facing local trial guide with actual acceptance evidence.
- [ ] T197 Supply the Ark key through a local secret file, restart the Windows instance with the approved chat/embedding models, and verify a real grounded `answer_brain` response plus vector index/search through the local bridge. EXTERNAL_VERIFICATION_PENDING until the key file exists.
