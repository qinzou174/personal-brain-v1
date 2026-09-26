# 验收记录：长文分块语义索引（2026-09-26）

关联设计：`docs/tasks/enhancement-20260926-长文分块语义索引.md`
代码提交：`a0d240c`（feat(retrieval) 长文分块语义索引）、`fd28508`（docs 接续收尾）

## 1. 背景与根因（复述）

RRF 单列表淹没（2026-09-26 实证）：一篇 15.4KB 交接文档对自己专属 token 词法 rank 1，却因全文单向量语义稀释进不了语义榜前 50，融合分 ≈1/61 被双榜卡（≥2/61）压出前 20。病灶在索引粒度（一文档一向量），不在融合公式——按拍板走分块方案，否决"融合层保底分"补丁路线。

## 2. 实现范围

| 层 | 文件 | 内容 |
|---|---|---|
| 迁移 | `migrations/versions/0015_search_index_chunks.py` | 块表：unique(entry_id, chunk_seq)、embedding VECTOR、父卡 CASCADE、owner RESTRICT |
| 切块器 | `personal_brain_infra/search/chunking.py` | ≥2000 字切块，600 字/100 重叠，段落贪心装包 + 超长段硬切（句末标点优先） |
| 写路径 | `search/indexer.py`、`search/repository.py`、`models/volcengine.py`、`digest.py` | index() 增 chunks 参数（delete-then-insert 天然处理重索引/墓碑）；embed_many 10/批批量；SECRET_REJECTED 整卡降级纯词法 |
| 检索路径 | `search/repository.py` | 语义榜双源合并：块表 DISTINCT ON 父卡取最小距离（=max 块分）+ 原整向量源；词法榜与 RRF 公式零改动（ER-03/#14 权威保留） |
| 授权 | 不复制 | 块表无 scope/sensitivity 列，全部 join 父卡（单一事实源） |

## 3. 测试证据（本机）

- 单测 `tests/unit/test_chunking.py`：8 项全绿（阈值边界/装包/重叠头/硬切/确定性）。
- 集成 `tests/integration/test_chunked_semantic.py`：10 项全绿，含 pre-fix 淹没形态复现（whole-vector 长文被 10 张双榜卡淹没）→ 分块后进前 10（语义 rank1 距离 0）；重索引无孤儿块；墓碑 CASCADE；scope/时间过滤继承父卡；_FakeEmbedder 无 embed_many 降级路径；秘钥降级。
- 全量回归：**645 passed / 12 skipped / 0 failed**（本机 PG 55432, brain_test）。
- 迁移链：4 处 EXPECTED_ORDER 清单补齐 0014+0015（含 head 断言改 0015），链完整性测试通过。
- 既有债修正：`tests/integration/test_governance_loop.py` L137 `== []` 断言过期（B-02 后 state=None 返回全部状态），git stash 对照确认非本次引入，改 `state="open"`。

## 4. 生产部署证据（192.168.10.7，/home/kms/deploy/personal-brain/prod）

- git pull 首试即中，HEAD 校验 `fd28508`；build api+worker → `up -d --build api worker migrate`。
- alembic_version = `0015_search_index_chunks`；`\d search_index_chunks` DDL 与设计一致（CASCADE/UNIQUE 约束齐全）。
- rebuild-index 回填：`{"scanned": 457, "enqueued": 457, "skipped_active": 0}`；队列排空后 rebuild_index 作业 **1258 succeeded / 1 cancelled / 0 failed**，dead_letter=0。
- 块回填结果：**69 块 / 7 卡**；分块父卡带整向量数 = 0（父卡 embedding 全部置 NULL ✓）。
- 最大分块文档：交接文档 825e2c94 → **22 块**；需求文档 11 块；自我档案 10 块。
- 2 张 live 卡无向量无块（a27516ff/zafiro 凭据打通笔记、740c3709/skill.md 全文存档）：内容含凭据类字样，属秘钥隔离预期（SECRET_REJECTED → 纯词法卡），非缺陷。
- `/doctor`（带 ops token）：`overall=healthy, failed_jobs=0, disk 78.2% free`。

## 5. 生产长文检索实测（MCP 真实链路，prod-trial @ 18083/mcp）

| 查询 | 结果 | 对比 |
|---|---|---|
| `MCP_SESSION_REQUIRED Trae` | 交接文档 **rank 1**，score 0.0325（双榜命中） | 修复前完全淹没（融合分 ≈0.0164 出前 20） |
| `RRF 单列表淹没 交接文档` | 交接文档 **rank 1**，score 0.0328 | 同上 |
| `get_entry_content(entry_id=ff039ce1…)` | 9682 字符全文返回 | 两步流程（搜索定位→取全文）闭环 |

## 6. 探针脚本

`deploy/windows-local/`：deploy_20260926_chunking.py（部署）、run_rebuild_index.py（回填）、wait_chunk_drain.py / verify_chunk_backfill.py / verify_chunk_final.py / verify_no_semantic.py（回填验证）、verify_chunk_search_live.py（MCP 实测）、diag_chunk_live.py（诊断）、doctor_chunk_deploy.py（健康检查）。

## 7. 遗留

无阻塞项。运维注意：后续新工具/迁移照常走"pull → up -d（migrate 自动）"，块表随父卡 CASCADE 无需额外清理。
