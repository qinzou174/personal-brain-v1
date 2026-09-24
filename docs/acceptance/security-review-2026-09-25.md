# 全项目安全审查（2026-09-25，live security review）

> Scope：全仓库（工作区 + git 全历史 + 部署配置 + 文档），用户 /goal 指定。
> 方法：TRAE-security-review（敏感信息全模式扫描 + 危险原语排查 + 部署面审计），
> 发现即修（用户明确授权"帮我让项目变安全"）。

## 发现与处置

| # | 类别 | 标题 | 严重度 | 置信度 | 证据（来源→去向） | 处置 |
|---|---|---|---|---|---|---|
| 1 | hardcoded_credentials | 18 个本机运维脚本硬编码 SSH 密码 | HIGH | 1.00 | `password="time.is.174"` → paramiko 直连生产 | ✅ 统一走 `_ssh.py`（`BRAIN_SSH_PASSWORD` env 或 gitignored `_local_creds.txt`）；全目录扫描零残留（commit `a22a91c`） |
| 2 | sensitive_data_exposure | 交接文档泄露本机测试库密码前 8 位并指引完整值位置 | MEDIUM | 0.85 | `brain:5f52a011...` + "完整值见 acceptance/历史命令" → 公开仓库 | ✅ 全打码 + 指引改为本地不入库文件（commit `1ccc731`） |
| 3 | authn_gap | `/doctor`、`/ready` 匿名暴露运行时细节（磁盘/死信/资产状态） | MEDIUM | 0.90 | 公网隧道与局域网匿名 GET → metrics/findings 全量返回 | ✅ 新增 `BRAIN_ENDPOINT_TOKEN_FILE` 门禁：匿名只见一位聚合，token 解锁全量，错 token 401（commit `520bc80`/`f6e7263`，生产已部署实测三态） |
| 4 | sensitive_data_exposure | 64 个一次性调试脚本长期滞留（含拓扑/凭据引用） | LOW | 0.85 | dbg_*/loop_*/verify_* 等 | ✅ 已删除（证据沉淀于 docs/acceptance） |

## 审查通过项

- **SSH 密码**：工作区 0 处、git 全历史 0 个 commit（早前"泄露进公开仓库"的判断为
  grep 误报，已更正——`provision_project_scope.py` 的 `PGPASSWORD` 来自本地不入库文件）
- **LLM key**：0 硬编码；`BRAIN_MODEL_API_KEY_FILE` 文件挂载；git 历史 `-S "sk-"`
  无真实 token（初始提交命中均为示例占位）
- **危险原语**：packages/apps 全域无 `eval` / `pickle.load` / 不安全 `yaml.load` /
  `shell=True` / `verify=False` / `debug=True`
- **SQL**：全 SQLAlchemy 参数化，无 f-string 拼接
- **路径遍历**：存储路径内容派生（sha256 切片），读取侧 `is_relative_to(root)` 防逃逸；
  `original_name` 仅作元数据
- **容器**：Dockerfile non-root（uid 10001）+ `uv sync --locked`；secrets 文件挂载
  （非 env 内嵌）；`read_secret_file` 带 regular/size/0600 权限校验
- **日志**：`RedactingFilter` 接线；死信摘要不落 payload 值
- **CORS**：默认空 allowlist（fail-closed）；会话 TTL 12h + 上限 512
- **公网暴露面**：nginx 仅路由 `/brain/mcp`；`/brain/doctor` 公网 404（局域网
  18083 直连是残余面，已由 #3 门禁覆盖）

## 部署注意事项（本次踩坑沉淀）

- compose **file secret 在 CLI 用户读不了 0600 源文件时会被静默跳过**（v5.3.1）：
  容器起来但 `/run/secrets/<name>` 缺失，服务 crash-loop `secret file unavailable`。
  ops token 因此改走**已验证的 model-proxy 目录 bind**
  （`/run/model-proxy/doctor_token`，源文件 10001:10001 0600）。
- bash -s 管道中 `docker compose exec -T` 必须加 `</dev/null`，否则吞掉脚本剩余 stdin。

## 遗留（需用户执行/拍板）

1. **轮换本机测试库密码**：`5f52a011` 前 8 位已随历史 commit 公开（完整值未入库）。
   `ALTER USER brain PASSWORD ...` 后同步 `E:\Personal-Brain-V1-local\secrets\db-dsn`。
2. **服务器 SSH 密钥化**：密码认证仍是弱面（密码未泄露但建议升级）；配好后可禁用
   密码认证，`_ssh.py` 改读私钥路径即可。

## 验证

- 全量回归 584+3（新增门禁测试 3 项）通过；生产部署后三态实测
  （匿名聚合/错误 401/正确全量）、`/mcp` 不受影响、dead_letter=0
- 工具链冒烟：重构后 `server_exec.py` 实连通过
