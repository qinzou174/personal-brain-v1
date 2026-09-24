# Feature Specification: Ranking Reasons 接线、Trilium 可选部署与本机模型激活

**Feature Branch**: `002-mcp-fixes`

**Created**: 2026-09-24

**Status**: Draft

**Input**: User description: "修复 Personal Brain V1 反思报告中的 Δ1 与 Δ2，并激活 T197。范围：1) Δ1 将 ER-03 要求的 ranking_reasons 真正接入检索排序输出；2) Δ2 在部署文件增加 Trilium 可选服务（默认关闭，关闭不影响核心）；3) T197 本机 Windows 实例激活真实模型（Ark Key，对话 deepseek-v4.1-flash，向量 doubao-embedding-vision）。约束：密钥不进 git/日志/文档；不破坏现有 431 passed 测试；部署改动向后兼容。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 检索结果可解释（Ranking Reasons）(Priority: P1)

当我通过搜索引擎或上下文问答获取结果时，我希望系统能说明"为什么这些内容排在前面"（如最新程度、置信度、来源可信度），以便判断结果的可靠性，而不是面对一个不可解释的排序。

**Why this priority**: 母提示词与 ER-03 要求检索可解释；无理由的排序会让用户无法信任 AI 返回的结果。

**Independent Test**: 调用检索工具，检查返回结果中每个命中的排序理由，确保理由与输入信号（时效/置信度/来源）相符。

**Acceptance Scenarios**:

1. **Given** 存在新鲜与过期、高置信与低置信的混合候选，**When** 执行一次语义/全文检索，**Then** 每个返回命中携带可读的排序理由，且理由反映其时效与置信度信号。
2. **Given** 检索命中数为 1 或为空，**When** 执行检索，**Then** 返回明确的单结果理由或空结果说明，不抛出异常。

---

### User Story 2 - Trilium 可选部署且不影响核心 (Priority: P2)

我希望在正式部署时可以选择启动/不启动 Trilium 人工笔记界面，且关闭它时，核心 Brain 的记忆、检索、权限、项目连续性全部不受影响。

**Why this priority**: 母提示词要求 Trilium 是"可移除的客户端"；部署位缺失会导致代码无宿主。

**Independent Test**: 使用可选配置启动整套服务，确认 Trilium 服务存在且健康；再以关闭 Trilium 的方式启动，确认核心服务照常。

**Acceptance Scenarios**:

1. **Given** 部署配置启用可选附加服务，**When** 执行容器编排启动，**Then** 附加服务正常创建且核心服务无依赖错误。
2. **Given** 部署配置关闭可选附加服务，**When** 执行容器编排启动，**Then** 核心服务全部健康，等待日志零错误，附加服务不创建。

---

### User Story 3 - 本机实例真实模型激活（T197）(Priority: P1)

我希望 Windows 本机实例能调用真实的大模型与向量模型，从而得到有真实生成的问答回答和真正的向量检索，而不是 fail-closed 的"未启用模型"。

**Why this priority**: T197 是拖尾外部门禁；激活后本机才算"真模型已接"。

**Independent Test**: 放置密钥文件，重启本机实例，发起一次真实问答与向量检索，确认命中有接地回答且检索命中非空。

**Acceptance Scenarios**:

1. **Given** 密钥已就位，**When** 重启本机实例，**Then** `/ready` 显示模型已启用，`answer_brain` 返回带真实生成的回答。
2. **Given** 存在已索引内容，**When** 执行带向量查询的检索，**Then** 返回向量命中结果且无权限/密钥错误。
3. **Given** 密钥文件缺失时，**When** 服务启动，**Then** 服务照常运行并保持"模型未启用"的诚实状态（fail-closed 不变）。

---

### Edge Cases

- 排序理由字段在既有消费方（如 Context Package 序列化）不存在时如何处理（向后兼容）。
- 附加服务镜像拉取失败时不阻塞核心服务启动。
- 密钥文件权限过宽或被他人可读时的安全告警。
- 模型密钥无效/过期时，接口返回明确的模型错误而非 500。
- 本机与局域网实例分开，本机激活不影响局域网现有配置。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 检索排序输出 MUST 为每个返回命中提供可读的排序理由，覆盖新鲜度、置信度、来源可信度等输入信号。
- **FR-002**: 排序理由 MUST 随检索结果序列化返回，且既有消费方兼容（无该字段时行为不劣化）。
- **FR-003**: 单结果或空结果 MUST 返回明确的理由说明，不抛异常。
- **FR-004**: 部署编排 MUST 提供可选的 Trilium 服务定义，默认不启用。
- **FR-005**: 关闭 Trilium 时，核心服务（API/Worker/DB）MUST 独立健康启动，零附加错误。
- **FR-006**: 本机实例 MUST 支持通过本地密钥文件启用真实对话与向量模型，文件缺失时保持 fail-closed 诚实状态。
- **FR-007**: 密钥值 MUST 不出现在 git、日志与任何文档中。
- **FR-008**: 本机模型启用后，`answer_brain` MUST 返回真实生成的回答，向量检索 MUST 返回非空命中。

### Key Entities *(include if feature involves data)*

- **RankedHit**: 检索命中对象，包含 object_id、score、reasons（排序理由）。
- **Context Package**: 返回给客户端的上下文包，需携带并可序列化排序理由。
- **Trilium 服务**: 部署层的可选容器服务，与核心服务解耦。
- **模型密钥文件**: 本机运行时的本地密钥源，仅存于运行时目录。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% 的检索返回结果路径覆盖排序理由字段（多结果、单结果、空结果），既有消费兼容零回归。
- **SC-002**: 变更后完整测试套件维持 431 passed / 0 failed（本机）；新增相关测试 ≥3 项并全绿。
- **SC-003**: 可选 Trilium 服务在启用/关闭两种模式下，核心服务健康、等待日志零错误。
- **SC-004**: 本机实例 `/ready` 显示模型已启用；`answer_brain` 返回真实回答，向量检索命中非空。
- **SC-005**: git 全历史扫描确认零密钥值泄漏。

## Assumptions

- 本机 Windows 实例与局域网实例是两个独立数据域；本机激活不影响局域网。
- 局域网已具备模型能力（已有 Ark Key），本次只激活本机。
- HTTPS/真实客户端矩阵（T186）不在本次范围；用户确认"http 后面放在服务器里面已有"。
- 现有测试基线的"431 passed"以本机实例为准。
- 排序理由格式向后兼容：新增可空字段，不破坏旧解析。

## Dependencies

- 现有 `retrieval/ranking.py`、`retrieval/compiler.py`、`protocols/remote.py`（序列化）代码结构。
- 部署协商：`deploy/compose.yaml` 使用支持 profiles 的 Compose 规范版本。
- 密钥放置位置 `E:\Personal-Brain-V1-local\secrets\model-api-key`；是否已存在于部署后可见。