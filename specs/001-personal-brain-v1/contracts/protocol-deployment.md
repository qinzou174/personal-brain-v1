# 协议、部署与外部验证契约

日期：2026-09-23。设计基线，不是已接入或已部署声明；实现时重新核验官方版本，Brain域不依赖客户端品牌。

## 认证与传输

- 本地Bridge使用stdio，stdout仅协议，日志stderr；远程使用HTTPS Streamable HTTP。旧SSE仅经真实客户端证明需要时增加。
- 私人ChatGPT远程入口采用授权码+PKCE S256、资源/授权服务器发现、精确redirect、resource/audience校验、最小scope和可撤销会话。单owner不豁免OAuth。CIMD/DCR/预注册取决于实际账户能力。
- 静态Bearer仅用于明确支持header的受控客户端，与OAuth分开；opaque描述token形式，不代表可省授权流。禁止上游token透传。
- 请求、读source、外部模型调用、canonical提交、回传前检查permission_epoch。MCP session ID不是权限；断线不自动回滚已提交事务。
- HTTP验证Origin、协议版本和session；外部仅TLS Brain，数据库/worker/admin不公开。TRAE/Cursor只生成无密钥模板，不跨产品复制变量语法。

## 实机验收矩阵

| 客户端 | 候选传输 | 必测 | 当前状态 |
|---|---|---|---|
| TRAE CN / 实际TraeCode版本 | stdio，HTTP按版本 | 中文路径、工具、写入、换账号恢复、拒绝越权 | EXTERNAL_VERIFICATION_PENDING |
| Cursor实际版本 | stdio/HTTP | 工具发现、跨IDE读取/决策、撤销 | EXTERNAL_VERIFICATION_PENDING |
| ChatGPT实际账户/模式 | HTTPS MCP+OAuth | 发现登录scope调用撤销及可达性 | EXTERNAL_VERIFICATION_PENDING |
| 合成A/B客户端 | 同业务契约 | MVP双端与权限自动测试 | 尚未实现；不能替代前三项 |

真实登录/2FA和密钥只在实施真实阻点由owner提供；本轮不需要。

## 业务接口与状态

22个核心工具见tool-contracts.md。还需受限owner接口：list_review_items/get_proposal/confirm/reject、get_operation_status、get_health、list/ack_notification、export/import preview；不开放SQL/admin。修改已有对象必须expected_version。

save_note需knowledge.write及scope；跨域抽取分别需要finance/todo等write，不能绕权。读默认20、范围1..100、query≤8000；区间[start,end)，UTC+原时区。分页游标绑定client/scope/filter/version且不含明文。

二进制经认证上传流取得同client绑定asset_handle，再由upload_asset引用；不把大文件塞1MiB JSON，不接任意URL或磁盘路径。completed仅同步操作结束，另标canonical_committed；accepted仅任务持久接收；pending_sync只为本地Bridge；partial显式warning；OUTCOME_UNKNOWN用原key查询。

## 中文检索和模型边界

PostgreSQL FTS+pgvector。中文由锁定版本应用分词器生成lexemes，查询同规则；未知词/中英/路径使用权限过滤后的索引词面补充，不扫描越权正文。固定中文fixture覆盖分词、未知词和中英混合，向量故障仍能关键词检索。

provider声明provider/model/version/dimensions/tokenizer/敏感度/出站许可/费用；未配置即禁外发。模型不判断SQL/权限/hash。新embedding维度独立索引，建成验证后切换，可回退；模型失败保留canonical并明确partial。

## Linux部署与恢复

目标Linux，Windows为开发/Bridge。/opt路径仅候选；Phase0核验OS/资源/Docker/服务/网络/端口/代理/隧道/Git/DB/Trilium/备份后冻结，不中断既有服务。Compose含API、worker、PostgreSQL+pgvector和Trilium集成；Gitea可选、Khoj不依赖。需非root、内部网络、卷、健康/重连、10MiB×5日志、资源限制和TLS代理；depends_on不能代替运行期重连。Linux脚本用.sh或跨平台Python，禁止chmod777/privileged/删库删卷救火。

pg_dump只保证数据库逻辑一致，不含资产/角色/Trilium/Git。备份冻结manifest cutoff，保护复制中的blob，包含无秘密角色定义、必要配置/Git/Trilium及删除ledger；恢复对外前先重放ledger。

## 官方复核门禁

本轮是文档核验，不是实机兼容。MCP以2025-11-25规范为可指认基线，不声称永久最新；实现锁定共同支持版本。

- [OpenAI认证](https://developers.openai.com/plugins/build/auth) 与 [远程MCP](https://developers.openai.com/api/docs/mcp)
- [MCP transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) 与 [authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization)
- [Cursor MCP](https://cursor.com/docs/mcp) 与 [TRAE添加MCP](https://docs.trae.cn/ide_add-mcp-servers)
- [Docker Compose启动顺序](https://docs.docker.com/compose/how-tos/startup-order/)
- [PostgreSQL 17逻辑备份](https://www.postgresql.org/docs/17/backup-dump.html)
