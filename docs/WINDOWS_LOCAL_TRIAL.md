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

当前本机尚无 Ark API Key 文件，因而 `answer_brain` 和向量检索未启用；
普通笔记、待办、费用、项目工具和中文全文检索可以试用。要启用用户此前指定的
DeepSeek 与豆包向量模型，将密钥单独保存为
`E:\Personal-Brain-V1-local\secrets\model-api-key`，然后执行关闭、启动脚本。
不要把密钥写入项目、TRAE 配置或聊天。启用后，笔记内容和检索问题会发送到
火山引擎 Ark 接口。

尚未验证独立备份与恢复，试用阶段请只使用合成内容，不导入不可丢失的个人资料。
