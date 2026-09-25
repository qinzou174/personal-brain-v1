# Research: 003-correction-delete-ux

## R1 笔记更正（O-02）——取代语义的落地形态

- **Decision**: 新工具 `update_note(old_note_id, content, requested_scope, idempotency_key)`。同一事务内：①按既有 save_note 管线写入新笔记（检索卡+抽取作业照常）②旧 raw_input 墓碑（lifecycle_state="deleted" + deleted_at）③删除旧条目的 search_index_entries 卡片。响应含新 record_id 与 superseded_id（旧 id），审计链路完整。
- **Rationale**: append-first 存储下"能改"的用户可见语义 = 旧内容退出检索视野 + 新内容生效；归档保留满足宪法 V（可追溯）。复用 _commit_record 的 side_effect 钩子（B-03 已验证该模式）。
- **Alternatives**: ①原行就地覆盖——违反宪法 II（原始输入不可静默替换）②只加标记不删卡——检索仍命中，未解决用户痛点。
- 注意：旧条目若已删除/不存在 → NOT_FOUND；新旧内容相同也执行（用户明确发起的更正，不走哈希折叠）。

## R2 待办删除（N-02）

- **Decision**: 新工具 `delete_todo(todo_id, expected_version, requested_scope, idempotency_key)`：校验版本 → todos 行 lifecycle_state="deleted" → 移除检索卡 → 审计。list_todos 排除 deleted。
- **Rationale**: 待办属低风险记录，与"完成"同级的直接终态即可，无需治理确认门禁（ER-06 高风险才门禁）。生产 todos 已有 lifecycle_state 列（B-05 发现），无迁移。
- **Alternatives**: 走删除计划（重、且用户要的是轻量直接删除）；state="voided" 新枚举（需 CHECK 迁移，收益低）。

## R3 账目更正（N-03）

- **Decision**: 新工具 `correct_expense(expense_id, new_amount, requested_scope, idempotency_key)`：读旧账（激活、属主）→ validate_money(新金额) → 旧账 lifecycle_state="deleted" → 经 _commit_record 写入更正账（description 前缀"更正"，version=旧+1，新 raw 源）→ 响应含 new/corrected_from。汇总（仅计激活行）自动正确。
- **Rationale**: 领域层 correct_expense 的 adjustment 语义与存储模型（按激活行聚合）不匹配；"旧账归档+新账生效"与笔记更正同构，且天然满足 ER-04 可追溯。
- **Alternatives**: 直接暴露 aggregate 语义的 adjustment 行——聚合符号语义与"更正为 X"的用户意图相悖，易产生双计/漏计。

## R4 时间范围检索（N-04）

- **Decision**: 检索卡元数据新增 `content_time`（raw_input 取 original_at，其余取源行 created_at）；search_brain 增可选 `time_from`/`time_to`（ISO 日期），在 PostgreSQL 检索 SQL 内过滤 `(metadata_filters->>'content_time')`；提供范围时无 content_time 的卡片诚实排除。既有卡片经 `rebuild-index` 管理命令回填。
- **Rationale**: 内容时间必须在索引行内可得才能不额外查源表；rebuild-index 已存在，回填无需新迁移。
- **Alternatives**: 检索后按源表逐条过滤（N 次额外查询）；只支持 raw_input（范围不完整）。

## R5 实时冲突提示（O-04）

- **Decision**: propose_self_claim 响应新增可选 `conflict_warning`：同属主、同 category、生命周期 active/candidate、极性相反（启发式：否定词判定）的既有主张存在时给出，含对方 claim_id 摘引。不阻止提交；每日 conflict_scan 仍是权威深扫。
- **Rationale**: 轻量提示要快——单条 SQL 同属主/同类别查询 + 极性词判定；不做向量相似。
- **Alternatives**: 复用 worker 的 conflict_scan（跨包依赖方向错误且是批处理）；向量相似比对（成本高、非本次范围）。

## R6 路由词表（O-08）

- **Decision**: router.classify_intent 的 todo_list 增补「要做的事/待办/该办的事/要办」等模式；expense_total 增补「买了什么/花了/开销/花费」等。全部为既有规则结构的词表追加，不改路由架构。
- **Rationale**: S-38 矩阵实测 3/5 自然说法掉 hybrid；词表追加是既有机制内的最小扩展。

## R7 同名项目提示（O-05）

- **Decision**: create_project 响应新增可选 `duplicate_name_hint`（同名存活项目的 id/名称列表），不阻止创建。

## R8 A 类语义（O-06）

- **Decision**: propose_self_claim 的 lifecycle：A → "active"（直接生效），B/C → "candidate"。生效画像/冲突扫描的行为随之自洽；既有 promote 作业对 active 行自然跳过。

## R9 已裁决语义（O-03）

- **Decision**: 新稳定错误码 `ALREADY_RESOLVED`（入 STABLE_CODES/_SAFE_MESSAGES）：对非 open 审核项的裁决返回该码（替代语义含混的 CONFIRMATION_REQUIRED）。HTTP 状态走既有默认 400 映射。

## R10 项目删除自授权

- **Decision**: grant_project_scope（创作者自授权）在 project.read/project.write 之外补 `review.write`@project:<id>。既有项目按需由运维 review-access 补授（生产 SIMTEST 清理已验证临时授权路径）。
- **Rationale**: 治理闭环的创建者完整权能；不放宽他人权限。
