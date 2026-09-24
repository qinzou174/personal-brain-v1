# Trilium integration setup (US12)

Status: **proposed, not activated**. The human-knowledge interface is removable;
disabling it leaves core Brain behavior intact. Real Trilium connection evidence
is an EXTERNAL_VERIFICATION_PENDING item pending owner-provided endpoint details.

## Required contract

- One-way paged idempotent import through ordinary intake/lineage policy.
- Every note keeps its source revision, checkpoint, conflict handling, secret
  filtering and backup coverage.
- No core-health dependency: the Brain serves normally while Trilium is down.
- Optional: source health and last-import status; automatic digests stay OPTIONAL.

## Activation gate

1. Owner provides a reachable Trilium endpoint and read credential through the
   dedicated secret file path (never env/Compose/Git).
2. The import job runs under the durable job lease/fencing contract.
3. Real-account import evidence is recorded before any production data write.

## 部署（Compose 可选服务，默认关闭）

`deploy/compose.yaml` 已提供 `profiles: ["extras"]` 的可选 trilium 服务，核心
服务（api/worker/db）不依赖它（FR-100）：

```bash
# 默认启动：仅核心服务，不创建 trilium
docker compose -f deploy/compose.yaml up -d

# 需要 Trilium 笔记界面时
docker compose -f deploy/compose.yaml --profile extras up -d trilium
```

- 数据位于独立卷 `trilium-data`，不进入 Brain canonical 存储。
- 关闭 Trilium 不影响记忆、检索、权限、项目连续性与备份恢复。
- 独立参考模板见 `deploy/trilium-compose.example.yml`。
- 真实 Trilium 端点的导入验收仍属 T186 EXTERNAL_VERIFICATION_PENDING
  （需可达的 HTTPS/OAuth 路由与真实账号证据；mock 不替代）。
