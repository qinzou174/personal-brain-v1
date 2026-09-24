# Research: MCP 修复与模型激活

**2026-09-24** | 本文件记录 Phase 0 设计决策，resolve 所有规范澄清项。

## 待澄清项与决策

### R1: ranking_reasons 如何接线、返回给谁
- **Decision**: 在 `RankedHit` 的 `reasons` 元组中写入结构化信号（freshness/confidence/source_trust 的输入与影响），由 `compiler.py` 直接复用 `rank_hits` 产出的 `RankedHit`（而不是自己另排序只在 compiler 内部按 freshness 排）；检索结果序列化时把 `reasons` 映射为 `ranking_reasons` 字段，**向后兼容**（旧消费方忽略新字段；字段为可空列表）。
- **Rationale**: compiler.py:26 当前 `sorted(...freshness...)` 是绕过 ranking.py 的原始排序，导致 RankedHit.reasons 从未被消费（stage-history 已有结论"ER-03 规定 ranking_reasons 代码零实现"）。让 compiler 消费 rank_hits 的真实输出即可同时修复排序与理由，最小改动且语义对齐 ER-03。
- **Alternatives considered**: 在 compiler 内补写 reasons 而不动排序（失败：reasons 与排序结果不一致）；在序列化层硬编码 reasons（失败：无输入信号）。

### R2: 排序理由的输入信号从哪来
- **Decision**: candidates 字典中已有 `freshness`、`confidence`、`source_trust`、`informaion_class` 键（retrieval 各源已提供）；`rank_hits` 增加对这些键的采集形成 reasons 元组，如 `("fresh", "confidence=0.9", "source=explicit")`。
- **Rationale**: 不改动数据获取层，只消费已有字段，最小 diff。
- **Alternatives**: 新建联合评分（过度设计）。

### R3: Trilium compose 怎么加、怎么默认关闭
- **Decision**: 在 `deploy/compose.yaml` 增加 `trilium` 服务段，带 `profiles: ["extras"]` 与 `restart: "no"`（实际交给 `profiles` 控制启动）；加入 `profiles` 后默认 `docker compose up -d` 不启动它；新增 `deploy/trilium-compose.example.yml` 供需要者参考。**不修改** api/worker/db 的依赖树。
- **Rationale**: Compose `profiles` 原生支持"默认不启动的可选服务"，向后兼容（现有 `up -d` 行为不变）；与 001 spec 的"可移除客户端"硬约束一致。
- **Alternatives**: 独立 compose 文件（用户要多跑一条命令）；env 开关（易被误开）。

### R4: 本机模型激活的具体路径与验证
- **Decision**: 密钥放入 `E:\Personal-Brain-V1-local\secrets\model-api-key`（文件名即变量 `BRAIN_MODEL_API_KEY_FILE` 指向），内容为 Ark API Key；`start.ps1` 检测到存在即置 `external_models_enabled=true`（沿用既有逻辑，stage-history 已注明"start.ps1 会自动检测"）。对话模型 `deepseek-v4.1-flash`、Base URL `https://ark.cn-beijing.volces.com/api/coding`；向量 `doubao-embedding-vision`、Base URL `https://ark.cn-beijing.volces.com/api/coding/v3`（与局域网实例一致）。验证：`/ready` → `answer_brain` 实询 → `search_brain` 带 query_embedding 向量命中。
- **Rationale**: 局域网已有同一套变量成功运行，本机仅差密钥文件；用真实用户给的模型名与 URL，不发明新值。
- **Alternatives**: 改 settings 默认值（破坏 fail-closed 诚实语义，拒绝）。

### R5: 兼容性/回归口径
- **Decision**: 全套 `pytest`（本机）保持 431 passed / 0 failed；新增测试覆盖：reasons 随检索返回、空/单结果 reasons、compose profiles 解析、密钥缺失 fail-closed。
- **Rationale**: 001 阶段承诺的回归基线。