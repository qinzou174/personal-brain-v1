# Contract: ranking_reasons 返回字段

**版本**: 1.0 | **适用**: `search_brain` / context package（`get_brain_context` / 检索结果）

## 目标

让聚类排序"为什么这些命中排前面"对客户端可见、可机检，满足 ER-03"ranking_reasons 写入并接线"。

## 字段定义

```json
{
  "ranking_reasons": ["fresh", "confidence=0.9", "source=explicit"]
}
```

- 类型：`array<string>`（**兼容写入**：允许为 `array<object>` 的升级版，`signal`+`value` 形式，客户端按宽松解析）
- 可空：允许缺失/`null`（旧服务端）；空数组表示空结果
- 顺序：与命中的输出顺序一致（第 N 个元素是第 N 个命中的理由）

## 信号字典（当前实现发送的值）

| 信号 | 值示例 | 含义 |
|---|---|---|
| fresh | `"fresh"` | 命中为当前有效（freshness == fresh） |
| stale | `"stale"` | 命中标记过期 |
| confidence | `"confidence=0.9"` | 派生置信度（存在时） |
| source | `"source=explicit"` / `"source=document"` / `"source=inference"` | 信息类/来源可信度 |
| single | `"single"` | 单命中（无足量排序信号） |
| rrf | `"rrf"` | 无额外信号时保留的默认理由 |

## 示例（search_brain 响应片段）

```json
{
  "result": {
    "structuredContent": {
      "hits": [
        {"id": "…", "content": "…", "ranking_reasons": ["fresh", "confidence=0.9", "source=explicit"]},
        {"id": "…", "content": "…", "ranking_reasons": ["rrf"]}
      ]
    }
  }
}
```

## 兼容与回归

- 旧消费方：无 `ranking_reasons` 概念 → 忽略新字段，行为零劣化
- 空结果：`"ranking_reasons": []`
- 单结果：`"ranking_reasons": ["single"]`
- 校验：schema 不允许额外必填字段；`additionalProperties: false` 的既有 schema 不受影响（新增字段在 structuredContent 内层输出，不进入 inputSchema）

## 验收挂钩

- 多命中检索 → 每个命中携带对应 reasons
- 单结果/空结果 → 不抛异常，返回 `["single"]` / `[]`
- 全套回归 431 passed