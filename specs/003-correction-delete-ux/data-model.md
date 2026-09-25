# Data Model: 003-correction-delete-ux

## raw_input（笔记更正）

| 字段 | 更正动作 |
|---|---|
| lifecycle_state | 旧条目：`active → deleted`（归档保留，原文可查）；新条目：`active` |
| deleted_at | 旧条目写入时间戳 |
| content_hash / content_text | 新条目独立生成 |

关系：响应返回 `{record_id(新), superseded_id(旧)}`；审计事件记录同一 correlation_id。

## todo（删除）

| 字段 | 删除动作 |
|---|---|
| lifecycle_state | `pending/completed 行 → deleted`（终态） |
| version | 删除校验用 expected_version，冲突返回 VERSION_CONFLICT |

list_todos 排除 deleted 行；检索卡同步移除。

## expense（更正）

| 字段 | 更正动作 |
|---|---|
| 旧行 lifecycle_state | `active → deleted`（保留金额/描述供追溯） |
| 新行 | `amount=更正金额`（validate_money 正数/numeric(20,4) 校验）、`description` 前缀「更正」、`version=旧行.version+1` |
| 汇总 | 仅计 lifecycle_state=active 行，天然反映更正 |

## self_claim（A 类语义 + 冲突提示）

| 字段 | 变更 |
|---|---|
| lifecycle_state | policy_class=A → `active`；B/C → `candidate`（不变） |
| 响应 | A/B/C 提交响应均可含 `conflict_warning`（同类别极性相反的既有主张引用） |

## search_index_entries（时间过滤 + 卡片移除）

| 字段 | 变更 |
|---|---|
| metadata_filters.content_time | 新增：ISO 时间串（raw_input=original_at；其余=源行 created_at）；rebuild-index 回填 |
| 检索过滤 | time_from/time_to 给定时按 content_time 过滤；无 content_time 的卡片诚实排除 |
| 卡片移除 | update_note/delete_todo/correct_expense 的旧卡在同事务删除 |

## permission_grants（项目删除自授权）

| 字段 | 变更 |
|---|---|
| grant_project_scope | 在 project.read/project.write 之外增发 `review.write`@project:<id>（allow, highly_private） |
