# 可执行规则基线（ER）

**日期**：2026-09-22。**性质**：需求工程阶段制定的 V1 默认规则，不是用户已确认的个人偏好或已实测的服务器能力。
这些规则是 spec、数据模型、契约和任务的规范性附件。改变产品边界须改需求；改变可配置数值须记录版本、理由和回归案例。部署数值须经过环境调查验证，不能把默认值当成环境事实。

## ER-01 权威、血缘与数据类别

“material derived”明确指所有持久化或用于回答/决策的抽取、摘要、标签、视觉描述、转录、embedding、候选偏好、Self Claim、Module Card、Digest、排名解释。都必须保留 source IDs、生成器/策略版本、时间、生命周期；不确定结论还须保留 confidence 与计算输入。未持久化且未参与决策的临时中间缓冲不强制单独建实体。

数据类别与来源是两个维度：information_class = fact / explicit_user_statement / observation / ai_extraction / ai_inference；source_kind 说明载体/来源。original_document 不等于“内容已客观证实”。EXIF GPS 是“文件声称的坐标”的来源事实，不是独立验证用户确在该地。

删除最后一个有效来源后，派生项转 orphaned，不得同时 active 或进入普通答案；剩余来源重算成功前标 recomputing 并退出检索。派生 scope 为来源权限的交集，敏感级别不低于最敏感来源；不得通过摘要洗掉权限。跨域聚合须全部来源获准。

## ER-02 A/B/C 与生命周期决策表

按优先级执行：权限/Secret 过滤 → C 高影响变更 → A 明确记住 → B 普通信号 → L0 无价值。

| 条件 | 动作 | 验收判断 |
|---|---|---|
| 未获准或含 Secret | 拒绝普通入库 | 无正文及派生物 |
| 价值观、哲学、自我身份、重大关系定义、重大长期原则改变（即使含“记住”） | pending_confirmation；显示准确变更及旧版本 | 绑定 proposal/version 的独立确认前 active 不变 |
| 明确记住普通事实、偏好或工作规则 | A，active，explicit_user_statement；不重复询问 | 来源是原话，不自动提升客观真实性 |
| 无明确记住的普通偏好/兴趣 | B，candidate | 一次旅行不生成永久人格标签 |
| 无长期价值且未明确记住 | L0 | 只保留无正文的处理状态 |

B 晋升默认 **同时**满足：至少 3 个不同 canonical 输入；跨至少 14 天；至少 2 种情境；至少一个直接用户表达（AI 重分析不算新证据）；无未解决直接反证；同一原文派生出的摘要/翻译只算 1 份。全部满足后 established，只表示“有证据的普通偏好”，仍须带时间、情境与不确定性，不能变为身份事实。

未满足任何一项留 candidate；存在反证转 review，当前使用时及时澄清。值/身份类永不因数量自动晋升。证据得分 low/medium/high 由上述条件决定，可附 score，但不是概率；不伪造 0.91 等统计置信度。

显式纠正使旧推断 superseded 并产生历史；A 类不因闲置自动降级。B established 超 180 天无新证据转 historical（可配置）；candidate 超 90 天无有效新证据转 expired，保留来源。temporary 必须显式 expires_at；未设置不得自行猜测到期。显式生日、Expense、Decision、确认的哲学不按年龄自动过期，用户删除优先。

Memory.lifecycle 与 SelfClaim.establishment 分离：lifecycle 为原文 8 状态；establishment = candidate / established / explicit；review = none / pending_confirmation / rejected。corrected 记录 correction 事件并用 superseded 生命周期，不新造矛盾主状态。数据模型中的旧展示词须映射到这三个字段。

## ER-03 上下文预算与排序

summary=2,000、normal=6,000、deep=12,000 token 上限（包括警告、来源和 JSON 文本）。客户端传更小预算取 min；不可通过 detail 放宽授权。已知 tokenizer 用精确计数；未知时 UTF-8 字节数作为保守占用单位并标记估算，不能声称模型 token 精确值。

首先分配权限范围说明、stale/conflict/low-confidence 警告及来源引用；再选当前任务/约束/下一步，继而相关模块、决定、证据片段，历史扩展最后。不够时删低排名内容并返回 omitted/continuation_ref；连必要元数据都装不下时返回 BUDGET_TOO_SMALL（不返回超限 ContextPackage）。所有成功包都必须满足预算，取消旧 99% 允许超限规则。

排名先做授权和状态硬过滤（deleted/orphaned/secret 排除），当前问题 fresh 优先、历史问题按时间选择；剩余候选默认用 60 常数的倒数排名融合 keyword/semantic 两路，再按显式来源等级、有效时间、importance、稳定 object_id 决胜；confidence/freshness 的输入和影响写入 ranking_reasons。分数不是事实保证。只拉当前所需子层级，不默认读所有私人材料。

## ER-04 时间、金额和结构化记录

客户端必须传 occurred_at 或保留原文与 capture_time；本项目工程显示时间默认 Asia/Shanghai，个人记录使用 owner_timezone（初始 Asia/Shanghai，可改，改变不重写旧事件）。“明天”以该输入 capture_time + 当时 timezone 解释；“下午”保留 12:00–18:00 时间窗，不伪造 15:00。时区缺失或夏令时歧义进入 review，金额/到期时间未明确不能假称写好结构化记录。

amount 为十进制定点 numeric(20,4)，>0；currency 为必填三位币种代码。无币种且 owner_default_currency 未设时进入 review；设好默认后回执显式说明采用该默认。退款为 kind=refund + positive amount + 可选原记录引用，汇总净额扣减；调整用 versioned correction，不覆盖审计。不同币种分组输出，不自动换汇；显式换汇请求须列来源/日期/汇率并单列换算合计。

Todo pending 可直接 completed 或 in_progress/cancelled；in_progress 可 completed/cancelled/pending。terminal 保留 completed_at/archived_at；重新打开创建 correction event + version，不删除历史。Task planned→active/cancelled；active→paused/completed/failed/cancelled；paused→active/cancelled；failed→active 需要显式 resume 并保留失败事件。Finalize 有未完成目标不得标 completed，须 paused/failed 并列剩余工作。

所有状态 mutation 做 expected_version 比较；同请求重复返回原结果，版本冲突不丢另一方内容。

## ER-05 文件、ZIP 与 Secret 边界

默认上传单文件 ≤100 MiB，文件名 ≤255 字符（显示名；不作存储路径）。V1默认格式白名单：PDF、DOCX、UTF-8 TXT/Markdown；JPEG、PNG、WebP；MP3、M4A、WAV、FLAC；ZIP。实际MIME与扩展名必须一致，其他格式进入unsupported/pending_review而非猜测解析。超限返回 PAYLOAD_TOO_LARGE，不截断原始字节。允许配置增大但先验证磁盘/内存预算。

ZIP 默认仅保留原包和受限 listing，不索引成员。listing ≤1,000 entries、30 秒、总输出 ≤1 MiB、名长 ≤512 字符。显式分析时：展开总量 ≤500 MiB、单成员 ≤100 MiB、展开比 ≤100:1、成员 ≤1,000、默认递归层数 0、作业 ≤60 秒；测量实际流量不能只相信 header。拒绝绝对路径、..、盘符/UNC、链接/设备项与加密包；不覆盖工作区。超过任一限制终止隔离作业，原包无静默损坏，返回具体限额名称且不泄露 Secret。

sensitivity=secret 只存在于预入库分类结果；普通内容表只能 normal/personal/private/highly_private。secret_skipped 审计可记录类型、规则、时间，不能存原值、可恢复片段或凭据哈希（认证服务自身 verifier 例外，属于专用控制面）。拒绝内容不进入普通备份。

上传先进入无检索/无备份/无模型调用的短期隔离区，完成格式对应检查后才提升 canonical；失败或不可扫描标 pending_review，不宣称 secret-free，24h 到期擦除暂存并返回未受理。压缩包安全检查成员的短期流式扫描不等于建立成员索引；检查超时同样不提升。图像/音频的未知隐藏秘密无法保证检测，文档明确检测覆盖边界；可识别的 OCR/转录候选必须通过 Secret filter 后才入普通派生库。opaque/encrypted 附件无 owner 审查结论不提升。上传成功后的原字节保持不变，不为过滤而偷偷改写原图/文档。

## ER-06 身份、授权与确认

scope 名称以 source §65 为准：personal、projects、finance、diary、music、project:<id>、module:<id>，此外 todo、asset、self 为能力 scope；project grant 不继承个人域，module grant 不能扩大父 project 权限。allow intersection + explicit deny 优先，sensitivity ceiling 与工具 allowlist 必须同时满足。对象 ID 存在性检查也在 scope 内。

内部 opaque token 仅用于允许该认证方式的客户端；远程客户端需要 OAuth 时由协议适配层完成身份授权映射，不能把“单用户”误当“不需要 OAuth”。撤销通过 permission_epoch 更新，新请求立即拒绝；运行中的作业在读取来源、外部调用、提交结果和发送响应前重新检查。旧上下文缓存键包括 client + epoch + scope + sensitivity，不能跨客户端复用。

确认记录由 owner 审阅通道产生，包含 operation、target IDs、payload_digest、expected_version、risk、expires_at。默认 15 分钟有效、单次消费、幂等重放只返回原结果。模型/导入文本中的“用户已确认”不是凭证。C 类变更始终确认；A/B 普通保存遵循 ER-02，不因“profile modification”泛化要求额外确认。通知只向 owner 已授权渠道按规则发送；任意新收件人/外部代发不在 V1 自动行为范围。

Rotation：新旧 token 可显式允许最多 24h 重叠；revoke 立即取消全部重叠。外部授权凭据按专用秘密存储管理，不进入 Brain。向量/FTS 查询权限谓词下推；缓存与返回 sources 再检查，不先扩大搜索后删除结果。

## ER-07 幂等、作业与断网

(client_id, operation, idempotency_key) 唯一。key 为随机 UUID，payload canonical digest 检查不同内容复用。保留结果/键至少整个记录生命周期；删除正文后保留不可逆请求键墓碑，不可保留有猜测风险的正文 digest。迟到重试返回 tombstone/deleted，不重新创建已删内容。

Job lease=60s、heartbeat=20s，最多 5 次尝试（包含首次），延迟 5s/30s/120s/600s + ≤20% jitter，之后 dead_letter；validation/permission/secret 错误不重试。claim_token 单调递增，旧租约提交被拒绝。成批任务独立保存进度，partial 不等于 success。所有 producer、worker 经过同样权限/Secret/版本门。

离线队列限 owner 主动启用的单机客户端，默认 1,000 条或 100 MiB，超限拒绝新保存，不能丢最老条目；受 OS 用户 ACL 保护且加密于系统凭据存储支持的密钥下。secret 预检发生在入队前；本地 key 不跨设备自动迁移。撤销客户端时停止重放并允许 owner 导出/删除队列，不借新 token 自动越权发送。回执区分 completed + persistence=canonical_committed、accepted(durable queued)、pending_sync(local only)、OUTCOME_UNKNOWN(timeout after possible commit)，后者仅用原键核对，不另建写请求。

## ER-08 工程新鲜度与当前源码

Bridge 基于当前 approved root 的 HEAD、status、相关路径 hash、rename/delete、dirty diff；不允许通过 junction/symlink 或 TOCTOU 改变最终访问对象。刷新以 observation_revision 为 CAS 条件；扫描中再次变化不能标 fresh。非 Git workspace 可用路径/hash，revision=null 且明示 no_git_history；远程无当前工作区观察时 freshness=unknown/stale，不能根据时间没过期声称 fresh。

查询即时对已映射的相关文件检查；watcher 只加速，不作唯一证据。HEAD 变更但相关 hash 未变无需重读全文；新增/删除目录只扫描该变化范围。确需手工全量重建须明确说明理由和范围。Bootstrap 必须输出 Profile、Module Map/Cards、Dependencies、API、DB、Config、Constraints、TODO、Risks；unknown 标明，不从旧文档推断成现状。当前代码是事实的使用门：client rules 要求改之前读取相关当前源码。

## ER-09 删除与备份复活控制

删除计划仅预览，不改变数据可见性；confirmed 后先将已确认目标退出普通检索，再跨来源、summary/embedding、Evidence、Relation、Cache、AssetLink、Job/outbox、离线重放键登记墓碑；未确认不得隐藏或删除任何目标。仅删除已确认对象，保留未命中源数据。shared blob 有其他活跃引用时不能删 bytes，并告知“仍被其他来源引用”；owner 要彻底删字节时重新列所有引用确认。

维护只含 opaque ID、deletion version/time 的删除账本，独立于可还原历史的备份并随备份更新；恢复后对外服务前必须重放删除账本，再重建索引。共享证据剩余支持重算，无支持 orphaned；secret/私密正文不能进入审计墓碑。

默认选择“生产立即清除 + 备份到期清除”：回执明确 production_purged 与 backup_purge_due，未到期不得声称“所有副本彻底删除”。用户要求立即彻底清除时列出受影响备份集，经确认重建无该内容的新恢复点，再删除旧集/使用可验证密钥销毁；无权或无法做到返回 deletion_pending/blocked，不伪装成功。资产引用计数不因备份存在而阻止生产清除，备份独立维护快照。

## ER-10 备份、恢复样本与容量

初始保留建议为 daily 7、weekly 4、monthly 3，均可配置；同一快照可占多标签但只计一次字节。环境阶段估算 B95（试验备份大小 p95，无样本时用 canonical 大小×1.2），可用备份预算 V=目标卷可用量−max(10 GiB,卷容量15%)，所需字节为各唯一集估算总和；超过 V 时报告容量冲突，调整有记录，禁止静默删唯一已验证恢复点。最少保留最近 2 个成功备份且至少 1 个已验证可恢复点；若不满足暂停非必要重处理并告警，不能借此拒绝首次初始化。

每日一致性导出 PostgreSQL（pg_dump）+同一 cutoff 的资产清单；上传/删除与快照协调锁或版本 cut 防 dangling references，备份必须涵盖 Trilium（接入后）及必要 Git authority/remote 引用、配置、schema 和删除账本。备份库必须使用owner控制的静态加密或等价加密卷，传输加密；恢复密钥通过独立受控流程保管，不明文混入导出。Portable export同样加密到owner指定目标，或在明确的本机受控目标生成后立即提示其敏感性。

默认 RPO≤24h、测试数据集 RTO≤4h（来自工程假设，目标机测量后调整并记录）；首次启用、每次 migration 及每月至少一次隔离 restore。验收 fixture 全部记录/hash/关系/权限用例比较，不能抽样避开失败；生产定期 verify 对全部 canonical 表 count + FK/lineage dangling 全检，每表按备份 hash 种子取 min(N,100) 记录逐字段比较。资产全量 manifest 存在性/size，全 hash 抽 min(N, max(100,ceil(N×1%)))，含每种 MIME 和所有最近新增/曾失败资产；轮换覆盖使 90 天内全部有 hash 证据。任一失败本轮 restore_verification=failed。

permission matrix 全测每类允许/拒绝/撤销；每种 Expense currency 各一精确聚合、Todo 各状态、Task active/paused/terminal、Self A/B/C/冲突/删除证据、所有根 Event 子树和删除账本至少各 1 路。记录 seed、样本 ID、预期/实际、计数、耗时、版本、revision、backup_id，不能只留 PASS。

## ER-11 通知与增长

默认仅 Todo deadline、sync/index failure、backup/storage/health failure。Todo 按 due window 起点提醒一次（无时间窗则约定当天 09:00 owner timezone，标记此调度规则不伪造 due_at）；相同 incident key=类型+对象+故障代次，10 分钟合并、60 分钟 cooldown、未恢复只每24h摘要一次，恢复或严重性升高可一次绕过。新事件不得被旧 cooldown 吞掉。owner 可配置静音；所有通知候选记录 suppression_reason。V1 内置 Inbox 是必有可见渠道，外部渠道需已配置，失败不让 core health 假绿。

日志默认每服务 10 MiB×5 文件，安全审计 90 天、成功 jobs 30 天、失败 jobs 90 天、通知历史 90 天、临时处理 24h；不删除 canonical 记录来满足磁盘配额。磁盘 free<15% warning、<5% critical，健康区分 DB/API/worker/index/backup/restore；模型宕机只降级 AI 派生，raw/SQL/已有安全检索继续工作，不能悄悄换云端模型外发私密数据。

## ER-12 模型接口与性能测量

模型/embedding provider 是可替换边界，声明 provider_id/model/version、维度、tokenizer、允许 sensitivity、timeout、计费预算和 owner 对外发送策略；未配置允许外发时不发送。默认任务 timeout=60s、最多 2 次模型请求（纳入 Job 5 次预算且避免层层重试放大），429 尊重 retry-after，失败保留 canonical 并标 derived_pending。维度不兼容新 index version，与旧 index 分开，禁止混距排序。

性能默认测量域为单 owner、10,000 records、1,000 text documents、100 module cards、5 并发、热缓存/冷缓存分开各 1,000 请求。目标 exact read p95≤300ms、normal compile p95≤2s（不含外部模型）、排队受理≤1s（不含上传字节）；超时率≤1%。百万对象/25万资产仅扩容假设，未经压测不作为已验证能力。SC-004 两分钟从“继续任务”发出至所有所需上下文到达并给出正确下一步，不含授权登录人工时间；fixture 两次新会话都须成功。

## ER-13 规范优先级与执行门

最新用户指令→constitution→spec及本 ER→data-model/contracts→plan→tasks。发现冲突须修订低级文档，不能悄悄按代码方便解释。工程默认不是 owner 画像数据。原文 §0–144 不缩减：追踪台账标明 mandatory、optional、V2 reserve 或 governance。真实服务器访问、产品实现和部署当前均未执行；此门不妨碍当前文档修复。
