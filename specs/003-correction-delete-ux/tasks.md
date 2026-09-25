# Tasks: 003-correction-delete-ux（笔记更正/删除与 AI 消费体验完善）

**输入**: specs/003-correction-delete-ux/{spec,plan,research,data-model}.md + contracts/mcp-tools.md

## Phase 1: Setup

- [x] T001 确认分支/目录：specs/003-correction-delete-ux 工件齐备（spec/plan/research/data-model/contracts/quickstart）

## Phase 2: Foundational（无阻塞前置，直接进入各 US）

## Phase 3: US1 笔记更正（P1）

- [x] T003 [US1] store.update_note：authoritative_store.py——_commit_record(operation=update_note, target=新 raw) + side_effect 墓碑旧 raw（lifecycle=deleted/deleted_at）+ 删除旧 search_index_entries 行；旧不存在 → NOT_FOUND
- [x] T004 [US1] service.update_note：authorized_tools.py——authenticate + knowledge.write 授权 + 调 store + 响应含 superseded_id/index_state
- [x] T005 [US1] 契约测试：tests/contract/test_correction_tools.py——更正后旧检索 0/新检索命中/get_entry_content 语义/重复更正 NOT_FOUND

## Phase 4: US2 待办删除（P1）

- [x] T006 [US2] store.delete_todo：版本校验 + lifecycle_state=deleted + 移除检索卡 + 审计；list_todos 排除 deleted
- [x] T007 [US2] service.delete_todo + 契约测试（删除后列表消失/重复删 NOT_FOUND/旧版本 VERSION_CONFLICT）

## Phase 5: US3 账目更正（P1）

- [x] T008 [US3] store.correct_expense：读旧账（激活/属主）→ validate_money → 旧账 tombstone → 经 _commit_record 写更正账（description 前缀「更正」、version=旧+1）→ 响应 corrected_from
- [x] T009 [US3] service.correct_expense（Decimal 非数字→VALIDATION_FAILED）+ 契约测试（汇总反映更正/非法金额 in-band 错误/NOT_FOUND）

## Phase 6: US4 索引提示（P2）

- [x] T010 _commit_record 的 outcome 增 `index_state: "pending"`（全部产生检索卡的写操作生效）

## Phase 7: US5 时间范围检索（P2）

- [x] T011 indexer：卡片 metadata_filters 增 content_time（raw_input=original_at；其余=created_at/now）
- [x] T012 repository.search 增 time_from/time_to 过滤（metadata JSON 内 content_time；给定时无 content_time 卡片排除）
- [x] T013 search_brain/search_project/get_brain_context 的 schema 与 _search_core 透传；rebuild-index 回填说明

## Phase 8: US6 实时冲突提示（P2）

- [x] T014 domain 极性 helper + store.propose_self_claim 查询同类别极性相反既有主张 → 响应 conflict_warning（不阻止）

## Phase 9: US7 项目删除自授权（P2）

- [x] T015 authority.grant_project_scope 增发 review.write@project:<id>；契约测试：创建者删除计划不再 SCOPE_DENIED

## Phase 10: US8 路由词表（P3）

- [x] T016 router.py 词表扩充（要做的事/待办/买了什么/花了等）+ 路由矩阵测试扩充

## Phase 11: US9 同名提示（P3）

- [x] T017 service.create_project 响应增 duplicate_name_hint（同名存活项目）

## Phase 12: US10 A 类语义（P3）

- [x] T018 store.propose_self_claim lifecycle：A→active；测试更新（A=active、B/C=candidate）

## Phase 13: US11 已裁决语义（P3）

- [x] T019 STABLE_CODES 增 ALREADY_RESOLVED + resolve_review_item 非 open → 该码；契约测试

## Phase 14: 注册与收尾

- [x] T020 tools.py 注册三新工具（34→37）+ __main__ implemented/UUID 字段
- [x] T021 全量回归 0 失败
- [x] T022 文档同步（MCP_TOOLS.md/tool-contracts.md/SKILL.md 37 工具）+ 部署 + 生产复测（quickstart 场景）

## 依赖

- T003→T004→T005；T006→T007；T008→T009；各 US 之间独立可并行
- T020 依赖全部服务实现；T021/T022 收尾

## MVP

US1+US2+US3（能改能删）即可独立发布，其余 US 为独立增量。
