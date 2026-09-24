# Personal Brain V1 使用指南（当前真实状态）

## 先说结论

Personal Brain V1 目前是一个可运行的后端与 MCP 工具服务，不是带网页界面的
成品应用。它不会自己弹出聊天窗口。日常入口应当是 TRAE、Cursor 或其他 MCP
客户端；客户端理解你的自然语言后调用 Brain 的工具，Brain 负责权威存储、权限、
精确查询、项目连续性和来源追踪。

当前服务已部署在局域网服务器 `192.168.10.7:18081`，PostgreSQL/pgvector、
API、后台 worker、owner/client 管理、项目授权以及本地 bridge 均已跑通。TRAE CN
配置文件也已加入 `personal-brain`，但正在运行的 TRAE 需要执行一次“重新加载窗口”
后才会读取新配置。独立异机备份尚未确定，所以目前只放入合成验收数据，不要导入
真实私人数据。

另有一个已启动的 Windows 本机试用实例，地址为 `127.0.0.1:18082`，数据与局域网
实例独立。其实际安装、启动和 TRAE 使用步骤见
[`WINDOWS_LOCAL_TRIAL.md`](WINDOWS_LOCAL_TRIAL.md)。

## 日常怎样使用

连接 MCP 客户端后，直接在客户端中表达意图即可。典型用法：

- “记住：我以后项目时间统一使用北京时间。” → 保存有来源的明确规则。
- “午饭 38 元，分类餐饮。” → 写入精确的 CNY 费用记录。
- “明天下午提醒我取快递。” → 新建待办，并保留时间窗而不是伪造具体时刻。
- “我这个月餐饮花了多少？” → 从结构化费用表精确汇总，不让模型估算。
- “搜索我之前记录的京都旅行。” → 在当前客户端权限范围内检索笔记与来源。
- “继续 Personal Brain 项目。” → 读取项目目标、活动任务、检查点、约束和下一步。

写入操作需要唯一的幂等键。正常情况下由客户端自动生成；重复发送同一个请求不会
创建两份记录。后台索引可能比权威写入稍晚完成，因此刚保存后应以
`canonical_committed` 回执为准，搜索结果可稍后出现。

## 服务如何组成

1. PostgreSQL/pgvector 保存权威数据、权限、作业和检索索引。
2. `personal_brain_server` 提供 `/mcp`、`/health` 和 `/ready`。
3. `personal_brain_worker` 处理索引、解析、恢复和通知等持久作业。
4. `personal_brain_bridge` 作为 TRAE/Cursor 的本地 stdio MCP 入口，把请求转给服务。

任何一个客户端都必须使用独立、可撤销的凭据。不要把凭据直接写进 MCP 配置；
配置中只放私有凭据文件的路径。

## 运维启动顺序

服务器使用 `deploy/compose.yaml` 启动，API 只发布到局域网地址，数据库和 worker
没有宿主机端口。日常确认服务状态可访问：

```text
http://192.168.10.7:18081/ready
```

开发或故障排查时，本地进程的启动顺序是：

```powershell
uv run alembic upgrade head
uv run python -m personal_brain_server doctor --preflight --json
uv run python -m personal_brain_server
uv run python -m personal_brain_worker
```

预检必须返回 `ready: true`，然后 `/ready` 应同时报告 database、worker、storage
为 `ok`。这只证明运行依赖可用，不代表真实客户端、备份或公网访问已经验收。

Bridge 需要三个环境值：

- `BRAIN_BRIDGE_CLIENT_ID`：这个客户端的身份标签；
- `BRAIN_REMOTE_MCP_URL`：局域网阶段为服务器的 `/mcp` 地址；
- `BRAIN_CREDENTIAL_FILE`：只含该客户端 bearer 凭据的私有文件路径。

然后由 MCP 客户端启动 `python -m personal_brain_bridge`。TRAE CN 当前配置位于
`%APPDATA%\Trae CN\User\mcp.json`，只引用凭据文件
`%USERPROFILE%\.personal-brain\trae-cn-credential`，不包含凭据正文。ChatGPT 网页端不能直接
访问家庭局域网地址；它需要另行批准的 HTTPS/OAuth 安全入口。

## 管理客户端和项目权限

这些命令应只由 owner 在服务器或受控运维环境执行。凭据只写入指定私有文件，
不会输出到终端：

```powershell
uv run python -m personal_brain_server provision-client --name <client-name> --client-type <client-type> --credential-file <private-file>
uv run python -m personal_brain_server rotate-client --client-id <client-id> --credential-file <new-private-file>
uv run python -m personal_brain_server revoke-client --client-id <client-id> --confirm-client-id <client-id>
uv run python -m personal_brain_server project-access --client-id <client-id> --project-id <project-id> --access read|write|none --confirm-client-id <client-id> --confirm-project-id <project-id>
uv run python -m personal_brain_server list-clients --json
```

新建项目后，如果该客户端还没有对应的 `project:<id>` 权限，后续任务操作会被拒绝；
由 owner 授予 `write` 或 `read` 后才能继续，`none` 会立即撤销该项目权限。

## 当前不能做什么

- 不能把本机或服务器同盘备份当作独立灾难备份。
- 不能把测试账户、模拟客户端或 HTTP 200 当作真实 TRAE/Cursor/ChatGPT/Trilium 验收。
- 未配置并明确允许外部模型时，不会把私人内容发送给模型供应商。

因此当前最诚实的使用方式是：先在 TRAE 重载窗口，用合成内容日常试用；确定独立
备份介质并完成一次恢复验收后，再导入真实个人数据。
