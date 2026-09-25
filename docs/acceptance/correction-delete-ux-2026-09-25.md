# 验收：003-correction-delete-ux（笔记更正/删除与 AI 消费体验 11 项）

日期：2026-09-25（部署至 4ab301e）｜生产：192.168.10.7:18083｜客户端：prod-trial

## 交付范围（specs/003-correction-delete-ux，工具面 34→37）

| # | 用户故事 | 实现 | 提交 |
|---|---|---|---|
| US1 | 笔记更正（取代语义） | `update_note`：新笔记走 save_note 管线，旧 raw 同事务墓碑+检索卡移除，响应 `superseded_id` | 10da9e5 |
| US2 | 待办删除 | `delete_todo`：版本栅栏直删，重复删 NOT_FOUND，旧版本 VERSION_CONFLICT | 10da9e5 |
| US3 | 账目更正 | `correct_expense`：旧账墓碑+新账生效（更正前缀/version+1），汇总即时正确 | 10da9e5 |
| US4 | 索引提示 | 卡片型写响应统一 `index_state: "pending"` | 10da9e5 |
| US5 | 时间范围检索 | `search_brain/search_project/get_brain_context` 增 `time_from/time_to`；卡片元数据 `content_time`；日期边界按 UTC 解释 | 10da9e5 |
| US6 | 实时冲突提示 | `propose_self_claim` 响应 `conflict_warning`（与夜扫共享 domain 极性规则 `memory/polarity.py`） | 10da9e5 |
| US7 | 项目删除自授权 | `grant_project_scope` 补 `review.write@project:<id>` | 10da9e5 |
| US8 | 路由词表 | 要做的事/待办事项/买了什么/花销/开支/花费等自然说法命中精确路由 | 10da9e5 |
| US9 | 同名提示 | `create_project` 响应 `duplicate_name_hint`（fail-soft） | 10da9e5 |
| US10 | A 类语义 | A 类主张 lifecycle=active 立即生效；B/C 保持 candidate | 10da9e5 |
| US11 | 已裁决语义 | 新稳定错误码 `ALREADY_RESOLVED`（STABLE_CODES 23→24） | 10da9e5 |

## 测试证据

- 全量回归：**565 passed / 74 skipped / 0 failed**（4ab301e 本地）
- 新增契约/存储测试 `tests/contract/test_correction_tools.py`（21 项）：更正闭环、删除幂等、账目汇总、时间归一化、授权矩阵、路由矩阵、极性共享、竞态收敛
- 受影响既有测试更新：ALREADY_RESOLVED ×3（authoritative_store/governed_deletion/governance_loop）、STABLE_CODES 24、工具面 37

## 生产复测（verify_003_corrections.py，18/18 PASS）

tools-37 / US1 笔记更正闭环（写→更正→旧检索 0 命中→新全文正确）/ US2 删除（列表消失+重复删 NOT_FOUND）/ US3 账目（corrected_from+汇总正确+0 元 in-band VALIDATION_FAILED）/ US5 时间过滤（未来 0、当日 1）/ US6 冲突提示指向首条主张 / US10 A 类 active / US11 二次裁决 ALREADY_RESOLVED / US8 todo@exact finance@exact / US9 同名提示。

## 生产复测暴露并修复的问题（4ab301e）

1. **墓碑-索引竞态（真 bug）**：旧源索引作业在墓碑提交前读到 active 源、在其后插卡，墓碑事务删卡 0 行未覆盖 → 旧错误内容持续可检索。修复（收敛点在最后写入者）：
   - 索引器 `source_gone` 分支删除该目标现存卡（缺源=无卡不变式）
   - `update_note`/`correct_expense` 为墓碑旧源追加兜底索引作业（`delete_todo` 天然已有）
2. **抽取死信**：墓碑源的 `extract_raw_input` 作业 dead_letter → 改声明性跳过 `skipped=source_gone`
3. 竞态产物清理：重置死信作业+补排收敛作业，`stale_card=0` 复测确认

## 生产终检

- /doctor（带 ops token）：**healthy**，components 全 healthy，failed_jobs=0，findings none
- 死信/失败作业：0 行
- US7 查库：两个新建项目 grant 均含 `review.write@project:<id>`（issuer=creator_self_grant）
- git：main 同步至 4ab301e；服务器 git pull --ff-only 校验通过

## 遗留与拍板项（2026-09-26 已全部执行完毕）

- ~~**385 张历史卡片无 `content_time`**~~：rebuild-index 已执行（451 个重建作业全部成功、死信 0），**live 卡 content_time 覆盖 414/414 = 100%**，时间范围检索实测正常（近 7 天窗口命中真实笔记）
- ~~**SIMTEST003 复测数据**~~：治理删除计划打包 28 个存活目标（4 项目/2 账目/6 画像主张/16 源记录）批准执行，36 行全部 deleted 终态（归档可追溯），**28 目标残留检索卡 = 0**

### 执行中发现并修复的 2 个缺口

1. **class_c_gate CHECK 缺 deleted 终态**（迁移 0014，commit 1240b54）：批准含 C 类画像主张的删除计划时，墓碑写被 0004 约束拒绝，整个计划回滚——治理链路删不掉 C 类主张。放宽加入 `'deleted'`（不放松"C 类不可跳过确认激活"本意）。
2. **digest 摘要卡缺 content_time**（commit 633bbec）：`_index_digest` 未传该参数，未来每日摘要卡已天然携带；存量 6 张按源行 derived_at 一次性回填。另清理 1 张孤儿卡（源已墓碑、卡残留——竞态收敛修复覆盖，415→414）。

