# 增强设计：长文分块语义索引（chunk-level semantic index）

- 日期：2026-09-26
- 状态：已拍板（用户批准：分块方案 / ≥2000字切块600字块 / max 聚合）
- 类型：检索架构增强（ER-03/#14 排序权威不动，只改喂给它的语义列表）
- 关联记忆：project_memory #14（长度归一化）、#41（get_entry_content）、#45（RRF 单列表淹没实证）

## 1. 背景与实证

2026-09-26 接续执行交接文档任务时实证：一份 15.4KB 交接文档
（trae-cn-mcp-session-20260926）词法榜 rank 1，但语义榜前 50 缺席，
RRF 融合分 ≈0.0164 被泛相关卡压出前 20，自述检索配方完全失效。
换中文概念词配方才救回语义榜（命中 #4）。

后期会有大量长文（交接文档、设计文档、归档），此问题会从个例变成常态。

## 2. 根因（病灶定位）

- **不是 RRF 的问题**：RRF 奖励双榜共识，行为正确；它只是暴露问题的地方。
- **不是词法的问题**：`ts_rank_cd/(1+ln(len))` 密度归一化对长文本来就工作正常。
- **是语义索引粒度的问题**：一篇长文只有一个 embedding。向量是全文几十个
  主题的"平均值"，查询其中某个具体小节时，余弦相似度必然被稀释，
  长文在语义榜结构性缺席 → RRF 单列表淹没。

结论：只要"一文档一向量"的粒度不变，任何融合公式都是治标。
在索引层消除盲区（分块），而不是在融合层打补丁（保底分）。

## 3. 目标 / 非目标

### 目标
1. 长文（≥2000 字）语义可检索：被命中的"小节"以自己的向量出场。
2. 词法榜、RRF 融合公式、路由矩阵**零改动**（ER-03/#14 权威保留）。
3. 授权（scope/sensitivity）、content_time 时间过滤对块级检索完全继承父卡，
   单一事实源，不复制授权列。
4. 墓碑/更新生命周期下块随父级联失效，不产生孤儿可检索块。

### 非目标
- 不改 RRF 公式、不加单列表保底分（明确否决的补丁路线）。
- 不改 get_entry_content 读路径（仍按父卡取全文，块只是索引单元）。
- 不做块级展示/引用定位（后续可选增强，本期不做）。

## 4. 方案设计

### 4.1 数据模型（迁移 0015）

新表 `search_index_chunks`（只存语义向量，不存授权列）：

```sql
CREATE TABLE search_index_chunks (
    id            UUID PRIMARY KEY,
    owner_id      UUID NOT NULL,
    entry_id      UUID NOT NULL REFERENCES search_index_entries(id) ON DELETE CASCADE,
    chunk_seq     INT  NOT NULL,
    chunk_text    TEXT NOT NULL,           -- 原文切片（非 fts_text，供调试/摘录）
    embedding     vector(N) NOT NULL,
    vector_model_version TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entry_id, chunk_seq)
);
CREATE INDEX ix_chunks_entry ON search_index_chunks(entry_id);
-- pgvector 近似/精确索引按现有 search_index_entries 同款策略
```

要点：
- `ON DELETE CASCADE`：父卡删除 → 块自动消失（数据库层兜底）。
- 块表**不带** authorized_scope/sensitivity/content_time —— 检索时 join 父卡取，
  授权与时间过滤永远以父卡为准，无漂移可能。
- 父卡被分块时 `search_index_entries.embedding` 置 NULL：
  稀释的"全文平均向量"不再参与语义榜，长文语义分完全由最佳块决定。

### 4.2 切块器（纯函数，可单测）

位置：`packages/infrastructure/personal_brain_infra/search/chunking.py`（新）

```python
CHUNK_THRESHOLD = 2000   # 字符；>= 则切块（可调常量，不动架构）
CHUNK_SIZE = 600         # 每块目标长度
CHUNK_OVERLAP = 100      # 相邻块重叠

def split_chunks(text: str) -> list[str]:
    """按段落边界优先切块；单段超长则按句号/换行硬切。
    返回有序块列表；text < CHUNK_THRESHOLD 时返回 [text]（不切块）。"""
```

规则：
1. 优先在段落（`\n\n`）边界切，块长接近 CHUNK_SIZE 时收口。
2. 段落超长按句末标点/单换行二段切；仍超长才按字符硬切。
3. 相邻块重叠 CHUNK_OVERLAP 字符，保证边界语义不断裂。
4. 对**原始文本**切块（切块发生在 `fts_text()` 之前，
   不受 fts_text token 去重影响——见 #14 教训）。

### 4.3 索引路径改动

`PostgresSearchRepository.index()`（repository.py L27-63）：

1. 文本 ≥ CHUNK_THRESHOLD → 切块，逐块 embedding（父卡 embedding=None）；
   文本 < 阈值 → 现状不变（父卡单向量）。
2. 先删后插扩展到块：写入父卡前 `DELETE FROM search_index_chunks WHERE entry_id
   IN (该 target 的现有行)`——沿用现有 delete-then-insert 幂等模式，
   重索引自然替换全部块。
3. embedding 调用按 provider 支持情况合并为批（一次 API 调多文本，
   保住 #16 的后台日配额 200 次/天；15KB 文档 25 块不能变成 25 次调用）。

`SearchIndexer`（indexer.py L216-279）：透传分块结果，`source_gone` 分支
删父卡行时依赖 CASCADE 清块（无额外代码，但需集成测试锁定）。

### 4.4 检索路径改动

`PostgresSearchRepository.search()`：

- **词法榜：一字不动**（L104-106）。
- **语义榜**：从"查父卡表"改为"查块表 join 父卡"，每父取最小距离（= max 块分）：

```sql
SELECT DISTINCT ON (c.entry_id)
       c.entry_id, e.*, c.embedding <=> :qvec AS distance
FROM   search_index_chunks c
JOIN   search_index_entries e ON e.id = c.entry_id
WHERE  e.owner_id = :owner AND e.authorized_scope = :scope
  AND  e.sensitivity IN (...) AND e.valid_to IS NULL
  AND  c.vector_model_version = :vmv
  -- 时间过滤沿用父卡 metadata_filters->>'content_time'（L78-86 同款表达式）
ORDER  BY c.entry_id, c.embedding <=> :qvec
LIMIT  50
```

- `DISTINCT ON (entry_id)` + 按距离排序 = 天然的 max 聚合：每个父卡
  以其最佳块的名次进入语义榜，随后 `rrf_fuse(keyword_rank, semantic_rank)`
  收到的语义列表就是"每文档一个位次"，与现状结构完全同构。
- 语义榜只查块表意味着：分块文档父行 embedding=NULL 本来就查不到自己；
  未分块文档不产生块行、行为与现状逐位一致。

### 4.5 生命周期与竞态（沿用既有收敛点）

| 场景 | 行为 |
|---|---|
| update_note 更正语义 | 父卡先删后插（新 entry_id）→ 旧块随旧行 CASCADE 消失，新块重写 |
| 源墓碑（删除/更正） | source_gone 删父卡行 → CASCADE 清块；晚到索引作业对墓碑源声明跳过（#43 现有机制不变） |
| rebuild-index | 现有 CLI 通道重跑，块随父卡重建 |
| 凭据/模型换版 | vector_model_version 隔离照旧，块表同列隔离 |

无需新的竞态处理代码——块的生命周期严格挂靠父卡行，
现有"最后写入者收敛 + 兜底索引作业"机制原样生效。

## 5. 参数汇总（均为常量，后续调参不动架构）

| 参数 | 值 | 依据 |
|---|---|---|
| CHUNK_THRESHOLD | 2000 字符 | 个人库大多数笔记不触发；拍板 |
| CHUNK_SIZE | 600 字符 | 拍板 |
| CHUNK_OVERLAP | 100 字符 | 拍板 |
| 聚合方式 | max（DISTINCT ON 最小距离） | 拍板 |
| 两榜容量 | 50/50 不变 | 现状 |

## 6. 测试计划（红测先行）

1. **单元**：`tests/unit/test_chunking.py` —— 切块边界（段落优先/超长硬切/重叠/
   阈值以下原样返回/空文本）。
2. **单元**：现有 `test_length_penalty.py`（28 项路由矩阵、长度归一化）
   全量回归必须零改动通过——证明 ER-03/#14 未被触碰。
3. **集成**（PG harness）：**把本次实例固化为回归用例**——写入 ≥2000 字长文
   （含与查询强相关但占比 <10% 的小节），断言该长文进入语义榜且融合后
   进 top N；同断言短文行为与改造前一致（不切块路径逐位等价）。
4. **集成**：墓碑→块级联（删源后块行 0 残留）、update_note 重写后旧块消失、
   时间过滤在块路径上与父卡 content_time 一致。
5. **真实环境**：embedder/PG 为环境门禁项，真实调用验证保持
   EXTERNAL_VERIFICATION_PENDING 纪律，部署后用生产长文实测（交接档复检）。

## 7. 迁移与回填

1. 迁移 0015（建表+索引），down_revision 接 0014。
2. 部署后 `python -m personal_brain_server rebuild-index --limit 5000`
   （api 容器内执行，既有通道）回填全部卡片块。
3. 回填验证：长卡块数 >0、父卡 embedding IS NULL、
   交接档配方 `search_brain("MCP_SESSION_REQUIRED Trae")` 命中前 5。

## 8. 风险与开放问题

| 风险 | 对策 |
|---|---|
| embedding 调用数放大 | 块批量化为一次调用；后台日配额监控（#16/#20 死信通知） |
| DISTINCT ON + 余弦排序的性能 | 个人库规模（万级块）B-tree+vector 索引足够；基准用 er12_benchmark 复测 |
| 块摘录与父卡 display_excerpt 不一致 | 摘要仍取父卡 text[:300]（L139 不动），块文本仅供索引 |
| 短文行为漂移 | 不切块路径零改动 + 集成测试逐位等价断言 |

开放问题（不阻塞实施）：块级引用定位（命中第几块）是否进入
get_entry_content 摘录窗口——记为后续可选增强。

## 9. 实施顺序

1. 迁移 0015（建表）
2. chunking.py + 单测（红）
3. index() 写路径（分块+批 embedding）+ search() 语义榜改块表（红测：长文回归）
4. 全量回归（路由矩阵/长度归一化/治理闭环既有 584 项）
5. 部署 + rebuild 回填 + 生产长文实测
6. 验收记录入 docs/acceptance/，project_memory 记条目
