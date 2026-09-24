"""Long-running worker lifecycle over fenced durable jobs."""

from __future__ import annotations

import inspect
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from time import sleep
from typing import Any, Mapping

import sqlalchemy as sa

from personal_brain_infra.jobs.store import (
    JobPolicy, claim_ready_jobs, complete_job, fail_job, heartbeat_job, update_job_progress,
)


@dataclass
class WorkerLoop:
    poll: Callable[[], None]
    wait: Callable[[float], None] = sleep
    poll_interval: float = 1.0

    def run(self, *, stop_requested: Callable[[], bool]) -> None:
        while not stop_requested():
            self.poll()
            self.wait(self.poll_interval)


class JobExecutionError(Exception):
    def __init__(self, code: str, *, retryable: bool, summary: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        # Value-free, owner-readable reason (FR-070/FR-073: no payload content).
        self.summary = summary


# One readable sentence per failure code so a dead letter explains itself in the
# job row and in the owner's inbox notification instead of a bare code.
FAILURE_SUMMARIES: dict[str, str] = {
    "NOT_FOUND": "引用的记录已不存在（可能已被删除）",
    "SECRET_REJECTED": "内容疑似包含凭据，按安全规则拒绝处理",
    "VALIDATION_FAILED": "请求字段不合法，作业无法执行",
    "TOOL_DENIED": "该客户端没有执行此作业所需的能力",
    "SCOPE_DENIED": "权限不足，作业被拒绝",
    "PERMISSION_DENIED": "权限不足，作业被拒绝",
    "SENSITIVITY_DENIED": "记录敏感级别超出该客户端授权上限",
    "CONFIRMATION_REQUIRED": "该操作需要主人确认后才能执行",
    "CONFIRMATION_EXPIRED": "确认已过期，需要重新发起",
    "AUTH_INVALID": "客户端凭据无效",
    "CLIENT_REVOKED": "客户端已被撤销",
    "VERSION_CONFLICT": "记录在作业执行期间已被修改，版本校验失败",
    "DEPENDENCY_CONFLICT": "依赖的数据状态冲突，可在下次重试中恢复",
    "BRAIN_UNAVAILABLE": "依赖服务暂不可用（模型或数据库）",
    "PAYLOAD_TOO_LARGE": "内容超出大小上限",
    "WORKSPACE_BOUNDARY_VIOLATION": "工作区根标识校验失败",
    "ARCHIVE_LIMIT_EXCEEDED": "归档数量超出上限",
}


def describe_failure(code: str | None) -> str:
    """A readable, value-free explanation for a failure code."""
    if not code:
        return "未记录失败原因"
    return FAILURE_SUMMARIES.get(code, f"{code}（未登记的原因，详情见 worker 日志）")


@dataclass(frozen=True)
class JobContext:
    heartbeat: Callable[[], bool]
    progress: Callable[[int, str], bool]


class DurableJobPoller:
    """Claim briefly, execute outside transactions, then settle under fencing."""

    def __init__(
        self, session_factory: Any, jobs: sa.Table, *, worker_id: str,
        handlers: Mapping[str, Callable[..., Mapping[str, Any]]],
        policy: JobPolicy | None = None,
        recheck: Callable[[dict[str, Any], str], None] | None = None,
    ) -> None:
        self._factory = session_factory
        self._jobs = jobs
        self._worker_id = worker_id
        self._handlers = handlers
        self._policy = policy or JobPolicy()
        self._recheck = recheck or (lambda _job, _phase: None)

    def _heartbeat(self, job: dict[str, Any]) -> bool:
        with self._factory.begin() as session:
            return heartbeat_job(
                session, self._jobs, job_id=job["id"], worker_id=self._worker_id,
                claim_token=job["claim_token"], policy=self._policy,
                now=datetime.now(timezone.utc),
            )

    def _progress(self, job: dict[str, Any], value: int, summary: str) -> bool:
        with self._factory.begin() as session:
            return update_job_progress(
                session, self._jobs, job_id=job["id"], claim_token=job["claim_token"],
                progress=value, summary=summary,
            )

    def _heartbeat_loop(self, job: dict[str, Any], stop: threading.Event) -> None:
        while not stop.wait(self._policy.heartbeat_seconds):
            if not self._heartbeat(job):
                return

    def _claim(self) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        claimed: list[dict[str, Any]] = []
        with self._factory.begin() as session:
            owners = session.scalars(sa.select(self._jobs.c.owner_id).where(
                ((self._jobs.c.state.in_(("queued", "retry_wait")) & (self._jobs.c.available_at <= now))
                 | ((self._jobs.c.state == "leased") & (self._jobs.c.lease_expires_at <= now))),
            ).distinct()).all()
            for owner_id in owners:
                claimed.extend(claim_ready_jobs(
                    session, self._jobs, owner_id=owner_id, worker_id=self._worker_id,
                    policy=self._policy, now=now,
                ))
        return claimed

    def poll(self) -> int:
        claimed = self._claim()
        for job in claimed:
            handler = self._handlers.get(job["job_type"])
            if handler is None:
                self._settle_failure(job, JobExecutionError("VALIDATION_FAILED", retryable=False))
                continue
            stop = threading.Event()
            thread = threading.Thread(target=self._heartbeat_loop, args=(job, stop), daemon=True)
            thread.start()
            try:
                self._recheck(job, "before_execute")
                context = JobContext(
                    heartbeat=lambda current=job: self._heartbeat(current),
                    progress=lambda value, summary, current=job: self._progress(current, value, summary),
                )
                parameters = inspect.signature(handler).parameters
                result = dict(handler(job, context) if len(parameters) >= 2 else handler(job))
                self._recheck(job, "before_commit")
            except JobExecutionError as error:
                self._settle_failure(job, error)
            except Exception as error:
                self._settle_failure(job, JobExecutionError(
                    "BRAIN_UNAVAILABLE", retryable=True,
                    summary=f"未预期的内部错误（{type(error).__name__}），详情见 worker 日志",
                ))
            else:
                with self._factory.begin() as session:
                    complete_job(
                        session, self._jobs, job_id=job["id"], claim_token=job["claim_token"],
                        result_refs=result, now=datetime.now(timezone.utc),
                    )
            finally:
                stop.set()
                thread.join(timeout=1)
        return len(claimed)

    def _settle_failure(self, job: dict[str, Any], error: JobExecutionError) -> None:
        summary = error.summary or describe_failure(error.code)
        with self._factory.begin() as session:
            fail_job(
                session, self._jobs, job_id=job["id"], claim_token=job["claim_token"],
                error_code=error.code, error_summary=summary[:512],
                policy=self._policy, now=datetime.now(timezone.utc), retryable=error.retryable,
            )
