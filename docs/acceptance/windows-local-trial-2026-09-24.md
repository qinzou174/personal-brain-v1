# Windows 本机运行验收（2026-09-24）

- 环境：Windows，项目路径 `E:\新建文件夹\Personal-Brain-V1`；便携 PostgreSQL 16.15
  与 pgvector 0.8.6 位于独立目录 `E:\Personal-Brain-V1-local`。
- 数据库只监听 `127.0.0.1:55432`；API 只监听 `127.0.0.1:18082`。
- `alembic upgrade head` 完成；doctor 和 `/ready` 均报告 database、worker、storage 为 `ok`。
- 独立 `brain_test` 数据库全量回归：429 passed，12 skipped。
- 实际 MCP HTTP 会话：initialize、30 项工具发现、`save_note` 返回
  `canonical_committed`；后台作业成功，中文查询返回 2 个命中。
- 实际 Windows stdio bridge 进程：3 个请求、3 个响应，30 项工具发现，中文检索 2 个命中。
- 再次保存合成笔记后 1 秒内完成索引；查询结果的 excerpt 与原文一致。
- `start.ps1` 实际运行，状态检查成功。TRAE CN 配置 JSON 可解析，本地凭据文件和
  命令路径存在；TRAE 窗口内的可见工具发现仍需用户重新加载窗口确认。
- `stop.ps1` 实际关闭本机 API/数据库；再次启动后 `/ready` 恢复为 `ready: true`，
  原有合成笔记仍可检索。
- 尝试读取正在运行的 TRAE CN 窗口：目标窗口存在，但截图接口连续两次返回
  `SetIsBorderRequired failed (0x80004002)`。因此未把窗口内的可见发现算作通过；
  用户需重新加载窗口并确认 `personal-brain-local` 出现在 MCP 工具列表。
- 模型密钥文件尚未在本机提供，因此本机真实模型回答和向量检索待验收。
- 本机试用数据库与既有局域网实例互相独立；没有导入真实个人数据。
