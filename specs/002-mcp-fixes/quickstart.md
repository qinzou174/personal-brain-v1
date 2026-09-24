# Quickstart: MCP 修复与模型激活 — 验证指南

> 本文件是验收运行手册；实现细节见 tasks.md 与实现阶段。所有命令在仓库根目录运行。

## 前置条件

- 本机实例运行中（`start.ps1`，uv 在 `C:\Users\槐至\.local\bin`）
- 局域网实例不受影响（本特征不改其代码路径，仅本机验证）

## 验证 1：ranking_reasons 接线（Δ1）

```powershell
$env:PATH = "C:\Users\槐至\.local\bin;" + $env:PATH
uv run pytest tests/unit/test_ranking_reasons.py tests/contract/test_ranking_contract.py -q
# 预期: 2 tests passed, 0 failed
```

并通过本机 MCP 手动抽查 `search_brain` 返回含 `ranking_reasons`：
```powershell
# 用 deploy/windows-local/mcp_smoke.py（或既有 probe）发起 search_brain
# 预期: 每个命中带 ranking_reasons, 多命中/单命中/空命中均不抛异常
```

**Given/When/Then**
- Given 新鲜+过期/高置信+低置信混合候选
- When 执行一次检索
- Then 每个命中携带可读理由且与信号一致

## 验证 2：Trilium 可选部署（Δ2）

```powershell
# 默认（不开 extras）—— 核心服务照常
docker compose -f deploy/compose.yaml up -d
docker compose -f deploy/compose.yaml ps
# 预期: api/worker/db 健康; 无 trilium 容器

# 开 extras —— 可选服务出现
docker compose -f deploy/compose.yaml --profile extras up -d
docker compose -f deploy/compose.yaml --profile extras ps
# 预期: trilium 出现且健康; 关闭核心不受影响
```

（若本机无 Docker，本项在局域网实例验证；脚本 `tests/contract/test_deployment_boundary.py` 校验 compose 解析。）

## 验证 3：本机模型激活（T197）

```powershell
# 1) 放置密钥（内容为 Ark API Key, 仅本地文件, 绝不入库/日志/文档）
#    目标路径: E:\Personal-Brain-V1-local\secrets\model-api-key

# 2) 重启本机实例
& "e:\新建文件夹\Personal-Brain-V1\deploy\windows-local\stop.ps1"
& "e:\新建文件夹\Personal-Brain-V1\deploy\windows-local\start.ps1"

# 3) 检查就绪状态（external_models_enabled 应为 true）
Invoke-RestMethod http://127.0.0.1:18082/ready

# 4) 真实问答
#    answer_brain("本机模型激活验证, 一句话总结", requested_scope="knowledge")
#    预期: 返回真实生成的回答（非 fail-closed）

# 5) 向量检索
#    search_brain(query="…", requested_scope="knowledge", query_embedding=[...],
#                 vector_model_version="doubao-embedding-vision")
#    预期: 命中向量结果非空, 无密钥/权限错误
```

**Given/When/Then**
- Given 密钥已就位
- When 重启本机实例并调用真实模型接口
- Then `/ready` 模型启用、answer_brain 真实回答、向量命中非空

## 验证 4：回归基线

```powershell
uv run pytest -q
# 预期: 431 passed / 23 skipped / 0 failed（或 ≥431 passed, 0 failed; 新增测试计入）
```

## 密钥安全核验

```powershell
Set-Location "e:\新建文件夹\Personal-Brain-V1"
git grep -n "4a151991" $(git rev-list --all) 2>$null   # 预期: 无输出
Select-String -Path "E:\Personal-Brain-V1-local\*.log" -Pattern "4a151991"  # 预期: 无输出
```

**Anti-regression 红线**: ① 密钥绝不入 git/日志/文档；② fail-closed 密钥缺失行为不变；③ 核心服务在 Trilium 关闭时仍健康；④ 431 passed 零回归。