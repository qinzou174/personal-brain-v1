# Acceptance — 路由准确性矩阵 + 检索链路延迟基准（2026-09-24）

> 补测目的：用户要求验证"链路而非节点"——路由准确性与真实链路延迟；并确认规则路由（非 LLM 路由）的准确性是否有测试背书。

## 1. 路由准确性矩阵（新增 28 项断言）

**测试文件**：`tests/unit/test_router_accuracy.py`

### 红测发现（真实缺陷）
`classify_intent` 原先用**宽泛子串**判断金额意图：

```python
if any(keyword in lowered for keyword in ("总额", "花了", "多少钱", "expense", "total")):
```

导致误判（红测 11 项失败）：

| 误判输入 | 被路由到 |
|----------|----------|
| "我花了多少时间做这件事" | expense_total（错，非钱） |
| "昨天花了3小时跑步" | expense_total（错） |
| "今天花了很多心思准备" | expense_total（错） |
| "total time spent on project" | expense_total（错） |
| "the total headcount is ten" | expense_total（错） |
| "TOTAL" / "花了"（孤立） | expense_total（错） |

违反 ER-04（金钱/时间类查询必须确定性路由、不让模型猜），且会把非金钱查询错送进精确记账路径。

### 结构化修复（非补丁，规则重设计）
`packages/domain/personal_brain_domain/retrieval/router.py`：金额意图改为"显式金额线索"模式：

```python
_EXPENSE_PATTERNS = (
    re.compile(r"总额|总支出|总开销|总花费|费用汇总|开销"),
    re.compile(r"多少钱|多少元"),
    re.compile(r"花.{0,4}(钱|元|块|¥)"),          # 花费必须带钱单位，排除"花时间/花心思"
    re.compile(r"expense|money"),
    re.compile(r"total\s+(amount|expense|cost|money|spend\w*)"),  # total 必须带金额词
)
```

同时补了原先缺失的金额词（总支出/总开销/费用汇总/多少元/花X块）。**边界策略**：无金额语境的"花了/total"保守路由回混合检索（不确定就不硬路由，符合 ER-04 精神）。

### 回归
- 矩阵：11 正例 + 10 反例 + 5 边界 = 28 项全 PASS
- 既有相关测试（test_context_compiler / capacity_and_chinese_search）：5 项 PASS
- **全套回归：482 passed / 0 failed**（此前 454 → 新增 28 项）

## 2. 检索链路延迟基准（真实链路，非节点）

**探针**：`deploy/windows-local/latency_probe.py`（真实 MCP 端点 `127.0.0.1:18082`，真实模型已激活）
**证据**：`docs/acceptance/retrieval-latency-2026-09-24/report.json`（N：search×30×2、answer×5、write×10；0 错误）

| 链路 | p50 | p95 | max | 含义 |
|------|-----|-----|-----|------|
| search_brain 语义生成路径 | **575ms** | 683ms | 768ms | 向量模型生成查询向量 + 混合检索 + RRF |
| search_brain 纯 DB 路径 | **126ms** | 143ms | 145ms | 跳过模型调用：FTS + pgvector 余弦 + RRF |
| answer_brain LLM 端到端 | **3.03s** | 3.11s | 4.27s | 证据检索 + LLM 生成回答 |
| save_note 写入链路 | **207ms** | 231ms | 438ms | 认证 + 幂等 + 入库 |

### 解读
- **模型在路径上的真实成本 ≈ 449ms**（语义 575ms − 纯 DB 126ms）＝向量模型远程嵌入调用；
- **answer_brain 的 3 秒**主要是 LLM 生成延迟，属预期（单次真实模型调用）；
- 纯检索链路（126ms）与写入链路（207ms）在合成数据规模下表现正常，与 ER-12 基准（精确读 p50≈88ms、中文 FTS p50≈75ms）口径一致；
- 语义状态确认 `semantic_status: "generated"`——向量模型确实在路径上，非 mock。

### 已知边界
- 数据量为合成小库（数百条），未做大库压测；pgvector 语义路径的"生成查询向量"成本会随并发上升（每次调用都走 Ark 远程 API）。
- answer_brain 采样 5 次为控制真实模型调用成本，p95 样本少，仅供参考。

## 3. 变更清单

| 文件 | 变更 |
|------|------|
| `packages/domain/personal_brain_domain/retrieval/router.py` | classify_intent 结构化规则（修复"花了/total"误判） |
| `tests/unit/test_router_accuracy.py` | 新增 28 项路由矩阵（正/反/边界） |
| `deploy/windows-local/latency_probe.py` | 新增延迟探针（可复用） |
| `docs/acceptance/retrieval-latency-2026-09-24/report.json` | 延迟证据 |

未提交 git；未触碰生产/局域网实例；探针只读本机合成实例。
