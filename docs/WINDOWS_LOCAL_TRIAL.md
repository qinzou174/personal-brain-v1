# Windows 本机试用

这个实例运行在当前 Windows 电脑上，和局域网服务器的 Brain 是两个独立数据集。
它没有单独的聊天网页；通过 TRAE CN 的 `personal-brain-local` MCP 工具使用。

## 已安装的本机实例

- 程序：`E:\新建文件夹\Personal-Brain-V1`
- 运行数据与凭据：`E:\Personal-Brain-V1-local`
- PostgreSQL 16 + pgvector：`127.0.0.1:55432`
- Brain API：`http://127.0.0.1:18082/mcp`
- 状态：`http://127.0.0.1:18082/ready`
- TRAE CN：新增 `personal-brain-local`，原有 `personal-brain` 仍指向局域网服务器。

启动：在项目目录执行 `./deploy/windows-local/start.ps1`。脚本会检查本机数据库、
启动后台处理与 API，再等待 `/ready` 成功。关闭：执行
`./deploy/windows-local/stop.ps1`。关闭不会删除数据库、笔记或客户端凭据。

在 TRAE CN 中执行“重新加载窗口”，确认 MCP 工具列表出现
`personal-brain-local`。然后可以说：

1. “请用 personal-brain-local 保存到 knowledge：青石计划的代号是星灯。”
2. “请用 personal-brain-local 搜索 knowledge 中的青石计划，给我来源。”
3. “请用 personal-brain-local 记录待办：明天下午取快递。”

保存回执中的 `canonical_committed` 表示权威记录已写入；搜索索引由后台异步处理，
通常稍后可见。试用库已放入少量合成笔记，不含服务器 Brain 的真实数据。

## 模型回答

本机已启用真实模型（T197，2026-09-24 验证）：密钥存放在
`E:\Personal-Brain-V1-local\secrets\model-api-key`（36 字符 Ark API Key，已由
`.gitignore` 的 `secrets/` 排除且位于仓库外），启动脚本检测到非空密钥后自动置
`external_models_enabled=true`。对话模型 `deepseek-v4.1-flash`、向量模型
`doubao-embedding-vision`（1024 维）。实测 `answer_brain` 返回真实接地回答、
`search_brain` 语义状态为 `generated` 且含向量命中。不要把密钥写入项目、TRAE
配置或聊天。启用后，笔记内容和检索问题会发送到火山引擎 Ark 接口。若删除该密钥
文件并重启，则回到 fail-closed 的"模型未启用"诚实状态。详见
`docs/acceptance/t197-local-model-2026-09-24.md`。

尚未验证独立备份与恢复，试用阶段请只使用合成内容，不导入不可丢失的个人资料。
