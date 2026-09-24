# Data Model: Ranking Reasons 与兼容字段

> 本特征不新建数据库表；仅新增**返回契约字段** `ranking_reasons`（可空序列化字段）与**内存对象**字段扩展。既有 schema/迁移链 0001..0012 不动。

## 1. 内存对象：RankedHit（扩展）

文件：`packages/domain/personal_brain_domain/retrieval/ranking.py`

| 字段 | 类型 | 含义 | 变更为 |
|---|---|---|---|
| `object_id` | object | 命中对象标识 | 不变 |
| `score` | float | RRF/排序得分 | 不变 |
| `reasons` | tuple[str, ...] | 排序理由（**新增采集信号**） | 由 `("single" | "rrf")` 扩为携带输入信号的元组，例如 `("fresh", "confidence=0.9", "source=explicit")`；单结果仍为 `("single",)` |

**reasons 信号采集规则**（candidates 字典中已有键，零新数据源）：
- `freshness == "fresh"` → 追加 `"fresh"`；否则追加对应状态
- `confidence` 数值存在 → 追加 `f"confidence={confidence}"`
- `source_trust` 或 `information_class` 存在 → 追加 `f"source={值}"`（如 `explicit` / `document` / `inference`）
- 无可用信号 → 保持 `("rrf",)` 或 `("single",)`

## 2. 返回契约字段：ranking_reasons

| 字段 | 类型 | 可空 | 说明 |
|---|---|---|---|
| `ranking_reasons` | list[str] \| Object[] | 可空 | 每个命中对应的排序理由列表；**向后兼容**：旧消费方无此字段时行为不变 |

序列化格式建议（与 reasons 元组对应）：
- 简单模式：`"ranking_reasons": ["fresh", "confidence=0.9"]`
- 允许实现为对象数组：`[{"signal": "fresh", "value": true}, {"signal": "confidence", "value": 0.9}]` —— 实现选一种，见 contracts/ranking-reasons.md

## 3. 状态机 / 生命周期

无状态机变更。空结果返回 `ranking_reasons: []`；单结果返回 `["single"]`。

## 4. 兼容矩阵

| 消费场景 | 是否有 ranking_reasons | 行为 |
|---|---|---|
| 多命中检索 | 有（新） | 携带 reasons |
| 单命中 | 有（新） | `["single"]` |
| 空结果 | 有（新） | `[]` |
| 旧客户端（无此字段概念） | 忽略 | 无劣化（向后兼容） |