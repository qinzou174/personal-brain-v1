# 增强：MCP 检索可读性——"找得到"必须"读得到"

- **状态**：`ACTIVE`（实现中，用户已授权："你自己决定，让自己高效使用"）
- **需求来源**：AI 消费者实测痛点（2026-09-25 会话）。search_brain 命中文档后仅返回 300 字符开头截断摘录，且无任何工具可按 entry_id 读取全文；answer_brain 只能诚实说"证据不足"。知识库自身亦记录了同类痛点（raw_input `05d1c328`「检索粒度的坑」）。
- **期望的用户可见效果**：AI（及一切 MCP 客户端）检索命中后能取到命中条目的**全文**；搜索摘录自动聚焦到**匹配位置**而非固定文档开头；现有客户端无需重新授权。
- **当前已验证行为**：摘录在索引时固定为 `text[:300]`（repository.py:41），检索时原样返回（repository.py:123）；`fts_text` 是分词去重词袋，不可作为全文源；全文只在各源表（raw_inputs.content_text 等）。
- **范围**：新增 1 个 MCP 工具 `get_entry_content`；search/answer/context 响应的 excerpt 字段升级为匹配感知窗口（契约形状不变，仅内容更优）。**排除**：不改变任何写入路径、不建新表、不动权限模型（复用 `search.read`）。
- **关联**：`requirement-20260925-日常日志需求化.md` 的 G7（检索粒度）受益于本任务，但两任务独立。

## 变更项

1. **问题**：命中后读不到全文。**证据**：本会话需求文档获取被迫用 answer_brain+get_brain_context 拼凑，尾部仍缺失。
2. **受影响面**：infra 搜索索引器（解析逻辑复用）、AuthoritativeStore（新读方法）、AuthorizedToolService（新方法 + 摘录水合）、工具注册表、运行时 UUID 转换表。
3. **方案**：
   - indexer.py 抽出模块级 `EntryTextResolver`（target_type→源表全文解析，SearchIndexer 复用之，消除未来双份漂移）；
   - store 新增 `get_entry_content(entry_id, storage, sensitivity_ceiling)`：属主过滤行 → 敏感度超 ceiling 返回 None（与搜索过滤同语义的诚实缺省）→ 解析源全文（源已删返回 None → NOT_FOUND）；
   - 服务层 `get_entry_content`：authenticate → 行级 scope 以 `search.read` 授权（复用既有授权，**客户端零重配**）→ 返回全文+元数据；
   - `_search_core` 响应水合：对前 5 条命中用源文本计算匹配居中的摘录窗口（domain/retrieval/snippets.py），无词法命中则保持原摘录；失败降级不阻断搜索。
4. **预期行为**：见"期望效果"；工具面 33 → 34。
5. **保护对象**：写路径、幂等语义、ER-03 排序权威（RRF 不动——水合只改 excerpt 字段内容）、权限模型、token/凭据。
6. **风险与回滚**：摘录内容变化可能影响依赖 `excerpt==text[:300]` 的测试（回归扫描）；新工具纯增量，回滚=从 implemented 集合摘除。
7. **验证**：契约测试（授权映射/scope 拒绝/ceiling 语义/源已删/水合窗口/降级），全量回归，生产部署后真机 fetch 实测。
8. **文档同步**：mcp-personal-brain SKILL.md、docs/MCP_TOOLS.md、tool-contracts.md、本档。
9. **用户确认**：方向已获明确授权（"你自己决定"）；提交/部署仍等用户拍板。

## 完成对账

| 期望效果 | 结果 |
|---|---|
| 新工具 `get_entry_content`（按 entry_id 取全文） | ✅ 服务方法 + store 方法 + 工具注册表（33→34）+ 运行时 UUID 转换 |
| 授权复用 `search.read`、落在条目自身 scope | ✅ 先属主安全读取行 → 以行 scope 授权（checkpoint_task 先例）；未知/超 ceiling/源已删 → 诚实 NOT_FOUND |
| 搜索摘录匹配居中 | ✅ `_with_snippets` 对前 5 条命中以源文本重建窗口（domain/retrieval/snippets.py，词法未命中/失败降级保持原摘录） |
| target_type→源表映射单一化 | ✅ indexer.py 抽出 `EntryTextResolver`（含方言 id_converter），SearchIndexer 与 store 共用 |
| 既有客户端零重配 | ✅ 权限面无新工具名（search.read），默认授权矩阵不变 |
| 测试 | ✅ 契约 10 项 + store 集成 1 项（sqlite 全场景：全文/超 ceiling/未知/superseded/墓碑源）；全量 538 passed / 0 failed |
| 文档同步 | ✅ MCP_TOOLS.md、tool-contracts.md（顺带修正 answer_brain 行为 2026-09-24 实况）、mcp-personal-brain SKILL.md（34 工具）、本档 |

**部署状态**：代码就绪，等待用户拍板提交与部署；部署后需真机验证 search → get_entry_content 链路（真实客户端，不 mock）。

**刻意不改动**：RRF 排序权威（ER-03）、写路径与幂等语义、权限模型、索引时 display_excerpt 生成逻辑（水合只改响应内容）、Windows bridge（另有修复，见会话记录）。
