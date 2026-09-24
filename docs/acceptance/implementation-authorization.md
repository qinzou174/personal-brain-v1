# Implementation authorization record

Date: 2026-09-23 (Asia/Shanghai)

## Owner instruction and scope

The owner instructed Codex in this project task: “使用相关skill 执行任务。并在额度快使用完毕时 停止任务并做任务标记，我换其他模型来接续任务”. This supersedes the earlier documentation-only boundary for work described in `specs/001-personal-brain-v1/tasks.md`. The requested scope is the Personal Brain V1 implementation in this workspace, following the project Spec Kit skills, constitution, specification, contracts and task order. The owner explicitly requests a durable handoff marker before usage limits are nearly exhausted.

## Excluded and separately gated actions

- Out-of-scope V1 capabilities remain excluded as defined in `spec.md` and the constitution.
- No other repository, server or private dataset is part of this instruction.
- The target Linux host, port/path ownership, existing services and deployment route are not identified yet. Phase 0 read-only evidence and a concrete deployment decision remain required before any target-host mutation.
- No production deletion, firewall/authentication change, volume removal or irreversible operation is authorized by this general instruction alone. Those actions require their task-specific target, impact, recovery and confirmation gates.
- Credentials are not requested or written into this record. Real account setup and secrets are requested only at the actual integration blocker.

## Review checklist decision

At implementation start, `engineering-readiness.md` had 40 unchecked items and `requirements.md` had 16 unchecked items. Their unchecked reviewer-owned markers remain unchanged. The owner's new instruction to execute the task list is treated as the instruction to proceed through the implementation skill's checklist gate; it is not represented as reviewer sign-off or as evidence that those quality checks passed.

## Current task state

T001 is complete with this record. T002 requires a target Linux host identity and read-only connection. Future completed tasks are marked individually in `tasks.md` only after their own evidence is verified. See the handoff marker in `docs/acceptance/implementation-handoff.md` for the latest continuation state.
