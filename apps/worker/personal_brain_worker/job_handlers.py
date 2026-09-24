"""Production registry for concrete durable job types."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import sqlalchemy as sa

from personal_brain_infra.assets.derivation import AssetDerivationService
from personal_brain_infra.search.indexer import SearchIndexer
from personal_brain_infra.storage.base import StorageBackend
from personal_brain_domain.common.errors import BrainError
from personal_brain_domain.security.secret_filter import detect_secret
from personal_brain_worker.claim_dedupe import make_dedupe_handler
from personal_brain_worker.digest import make_digest_handler
from personal_brain_worker.evolution import (
    make_conflict_handler, make_promote_handler, make_retention_handler,
)
from personal_brain_worker.extraction import make_extract_handler
from personal_brain_worker.runtime import JobExecutionError


def build_job_handlers(session_factory: Any, tables: Mapping[str, sa.Table],
                       storage: StorageBackend, gateway: Any | None = None,
                       embedder: Any | None = None, *,
                       llm_daily_quota: int = 200,
                       timezone_name: str = "Asia/Shanghai") -> dict[str, Any]:
    indexer = SearchIndexer(session_factory, tables, embedder=embedder)

    def index(job, context):
        context.progress(10, "loading canonical source")
        try:
            result = indexer.handle(job)
        except Exception as error:
            code = getattr(error, "code", "BRAIN_UNAVAILABLE")
            raise JobExecutionError(code, retryable=code == "BRAIN_UNAVAILABLE") from error
        context.progress(100, "index committed")
        return result

    def provider_derive(job, context):
        """Bounded model call for AI/embedding derivation (ER-12).

        Provider execution stays fail-closed: without a configured gateway this
        handler refuses before any external call.  With one, the gateway enforces
        call counting, timeout, declared sensitivity/context budgets and secret
        rejection; a failure does not claim completion (FR-084) and the error is
        value-free (FR-070/FR-073).
        """
        from personal_brain_infra.models.gateway import ModelGateway, ProviderCallBudget

        if not isinstance(gateway, ModelGateway) or gateway.provider is None or gateway.card is None:
            raise JobExecutionError("TOOL_DENIED", retryable=False)
        try:
            target_type, raw_id = job["payload_ref"].split(":", 1)
            if target_type != "derivation":
                raise ValueError
            derivation_id = UUID(raw_id)
            owner_id = UUID(str(job["owner_id"]))
        except (ValueError, AttributeError) as error:
            raise JobExecutionError("VALIDATION_FAILED", retryable=False) from error
        with session_factory() as session:
            row = session.execute(sa.select(tables["derived_contents"]).where(
                tables["derived_contents"].c.id == derivation_id,
                tables["derived_contents"].c.owner_id == owner_id,
            )).mappings().one_or_none()
        if row is None:
            raise JobExecutionError("NOT_FOUND", retryable=False)
        context.progress(20, "provider call budget acquired")
        try:
            result = gateway.execute(
                {"derivation_id": str(derivation_id), "kind": row["kind"]},
                {key: row[key] for key in gateway.card.allowed_context_keys if key in row},
                sensitivity=row["sensitivity"], budget=ProviderCallBudget(max_calls=gateway.max_calls),
            )
        except BrainError as error:
            # Bounded failures surface as durable job outcomes, not silent claims
            # of completion: transient provider failures retry inside the Job
            # budget, policy rejections never retry (FR-083/FR-084, ER-12).
            raise JobExecutionError(
                error.code, retryable=error.code in {"BRAIN_UNAVAILABLE", "DEPENDENCY_CONFLICT"},
            ) from error
        context.progress(100, "provider derivation completed")
        return {"derivation_id": str(derivation_id), "provider_result": result}

    def parse_asset(job, context):
        try:
            target_type, raw_id = job["payload_ref"].split(":", 1)
            if target_type != "asset":
                raise ValueError
            asset_id, owner_id = UUID(raw_id), UUID(str(job["owner_id"]))
        except (ValueError, AttributeError) as error:
            raise JobExecutionError("VALIDATION_FAILED", retryable=False) from error
        assets = tables["assets"]
        with session_factory() as session:
            row = session.execute(sa.select(assets).where(
                assets.c.id == asset_id, assets.c.owner_id == owner_id,
            )).mappings().one_or_none()
        if row is None:
            raise JobExecutionError("NOT_FOUND", retryable=False)
        if not (row["media_type"].startswith("text/") or row["media_type"] in {"application/json", "application/xml"}):
            raise JobExecutionError("VALIDATION_FAILED", retryable=False)
        context.progress(20, "verified original bytes")
        service = AssetDerivationService(session_factory, tables, owner_id=owner_id, storage=storage)
        result = service.process(
            asset_id=asset_id, kind="extracted_text", generator_kind="parser",
            generator_version="bounded-text-parser-v1", transform=lambda content: content,
        )
        context.progress(100, "derived content committed")
        return result

    def inbox_only(job, context):
        context.progress(100, "durable inbox item available")
        return {"notified": "owner_inbox", "payload_ref": job["payload_ref"]}

    def reconcile_deletion(job, context):
        try:
            target_type, raw_id = job["payload_ref"].split(":", 1)
            if target_type != "deletion_plan":
                raise ValueError
            plan_id, owner_id = UUID(raw_id), UUID(str(job["owner_id"]))
        except (ValueError, AttributeError) as error:
            raise JobExecutionError("VALIDATION_FAILED", retryable=False) from error
        plans, actions = tables["deletion_plans"], tables["deletion_actions"]
        removed_search = removed_derived = removed_edges = 0
        with session_factory.begin() as session:
            plan = session.execute(sa.select(plans).where(
                plans.c.id == plan_id, plans.c.owner_id == owner_id,
                plans.c.execution_state == "completed",
            )).mappings().one_or_none()
            if plan is None:
                raise JobExecutionError("VERSION_CONFLICT", retryable=False)
            rows = session.execute(sa.select(actions).where(
                actions.c.plan_id == plan_id, actions.c.owner_id == owner_id,
            )).mappings().all()
            for row in rows:
                result = session.execute(tables["search_index_entries"].delete().where(
                    tables["search_index_entries"].c.owner_id == owner_id,
                    tables["search_index_entries"].c.target_type == row["target_type"],
                    tables["search_index_entries"].c.target_id == row["target_id"],
                ))
                removed_search += result.rowcount
                result = session.execute(tables["derived_contents"].delete().where(
                    tables["derived_contents"].c.owner_id == owner_id,
                    tables["derived_contents"].c.target_type == row["target_type"],
                    tables["derived_contents"].c.target_id == row["target_id"],
                ))
                removed_derived += result.rowcount
                edges = tables["derivation_edges"]
                result = session.execute(edges.delete().where(
                    edges.c.owner_id == owner_id,
                    sa.or_(
                        sa.and_(edges.c.source_type == row["target_type"], edges.c.source_id == row["target_id"]),
                        sa.and_(edges.c.derived_type == row["target_type"], edges.c.derived_id == row["target_id"]),
                    ),
                ))
                removed_edges += result.rowcount
            session.execute(plans.update().where(plans.c.id == plan_id).values(
                reconciliation_state="completed", updated_at=datetime.now(timezone.utc),
            ))
        context.progress(100, "deletion dependents reconciled")
        return {"removed_search": removed_search, "removed_derived": removed_derived,
                "removed_edges": removed_edges}

    def health_check(job, context):
        """Collect health evidence and raise one deduplicated inbox notice.

        FR-089..FR-091/ER-11: only explicit triggers may notify; detection and
        notification stay separate, the 60-minute cooldown merges a repeated
        failure, and a healthy brain produces no notification at all.
        """
        from personal_brain_domain.operations.notification_policy import decide_send
        from personal_brain_domain.operations.notification_triggers import evaluate_trigger

        owner_id = UUID(str(job["owner_id"]))
        moment = datetime.now(timezone.utc)
        notified = False
        with session_factory.begin() as session:
            failed_jobs = session.scalar(sa.select(sa.func.count()).select_from(tables["jobs"]).where(
                tables["jobs"].c.owner_id == owner_id, tables["jobs"].c.state == "dead_letter",
            ))
            stale_modules = session.scalar(sa.select(sa.func.count()).select_from(tables["module_cards"]).where(
                tables["module_cards"].c.owner_id == owner_id, tables["module_cards"].c.freshness == "stale",
            ))
            failed_jobs, stale_modules = int(failed_jobs or 0), int(stale_modules or 0)
            if failed_jobs:
                notifications, jobs = tables["notifications"], tables["jobs"]
                # Why they failed, in owner-readable words (value-free: codes and
                # sentences only, never payload content).
                from personal_brain_worker.runtime import describe_failure

                reason_rows = session.execute(sa.select(
                    jobs.c.error_code, sa.func.count(),
                ).where(
                    jobs.c.owner_id == owner_id, jobs.c.state == "dead_letter",
                ).group_by(jobs.c.error_code)).all()
                reasons = "；".join(
                    f"{describe_failure(code)}×{int(count)}" for code, count in reason_rows[:3]
                )[:300]
                decision = evaluate_trigger(trigger_type="brain_health_failure", risk="high")
                dedupe_key = f"brain_health_failure:{owner_id}:{moment:%Y-%m-%d}"
                last_sent = session.scalar(sa.select(sa.func.max(notifications.c.created_at)).where(
                    notifications.c.owner_id == owner_id,
                    notifications.c.dedupe_key == dedupe_key,
                ))
                minutes_ago = 10**6 if last_sent is None else (moment - last_sent).total_seconds() / 60.0
                if decision.notify and decide_send(
                    dedupe_key=dedupe_key, last_sent_minutes_ago=minutes_ago, cooldown_minutes=60,
                ).send:
                    notification_id = uuid4()
                    session.execute(notifications.insert().values(
                        id=notification_id, owner_id=owner_id, trigger_type="brain_health_failure",
                        source_object_id=None, risk="high", priority=decision.priority,
                        dedupe_key=dedupe_key, cooldown_group="brain_health", channel="inbox",
                        state="queued",
                        reason=(f"failed_jobs={failed_jobs} stale_modules={stale_modules}"
                                + (f"；原因：{reasons}" if reasons else "")),
                        delivered_at=None, acknowledged_at=None,
                    ))
                    session.execute(jobs.insert().values(
                        id=uuid4(), owner_id=owner_id, client_id=None,
                        job_type="dispatch_notification",
                        payload_ref=f"notification:{notification_id}",
                        idempotency_key=uuid5(NAMESPACE_URL, f"brain-health-notify:{notification_id}"),
                        state="queued", priority=0, attempts=0, max_attempts=5,
                        available_at=moment, claim_token=0,
                    ))
                    notified = True
        context.progress(100, "health evidence collected")
        return {"failed_jobs": failed_jobs, "stale_modules": stale_modules, "notified": notified}

    def dispatch_notification(job, context):
        try:
            target_type, raw_id = job["payload_ref"].split(":", 1)
            if target_type != "notification":
                raise ValueError
            notification_id, owner_id = UUID(raw_id), UUID(str(job["owner_id"]))
        except (ValueError, AttributeError) as error:
            raise JobExecutionError("VALIDATION_FAILED", retryable=False) from error
        notifications = tables["notifications"]
        with session_factory.begin() as session:
            result = session.execute(notifications.update().where(
                notifications.c.id == notification_id, notifications.c.owner_id == owner_id,
                notifications.c.state == "queued",
            ).values(state="delivered", delivered_at=datetime.now(timezone.utc),
                     updated_at=datetime.now(timezone.utc)))
            if result.rowcount != 1:
                raise JobExecutionError("VERSION_CONFLICT", retryable=False)
        context.progress(100, "owner inbox notification delivered")
        return {"notification_id": str(notification_id), "delivered": True}

    def prune_rebuildable(job, context):
        owner_id = UUID(str(job["owner_id"]))
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        with session_factory.begin() as session:
            result = session.execute(tables["jobs"].delete().where(
                tables["jobs"].c.owner_id == owner_id,
                tables["jobs"].c.state.in_(("succeeded", "cancelled")),
                tables["jobs"].c.finished_at < cutoff,
            ))
        context.progress(100, "bounded retention applied")
        return {"pruned_jobs": result.rowcount}

    extract = make_extract_handler(
        session_factory, tables, storage, gateway, quota=llm_daily_quota,
        timezone_name=timezone_name,
    )
    digest = make_digest_handler(
        session_factory, tables, storage, gateway, embedder, quota=llm_daily_quota,
        timezone_name=timezone_name,
    )
    return {
        "extract_raw_input": extract, "index_raw_input": index, "index_todo": index,
        "index_self_claim": index, "bootstrap_project": index,
        "refresh_project_context": index, "parse_asset": parse_asset,
        "reprocess_asset": parse_asset, "notify_review": inbox_only,
        "rebuild_index": index, "reconcile_deletion": reconcile_deletion,
        "health_check": health_check, "dispatch_notification": dispatch_notification,
        "retention_maintenance": prune_rebuildable, "provider_derive": provider_derive,
        "promote_candidates": make_promote_handler(session_factory, tables),
        "retention_sweep": make_retention_handler(session_factory, tables),
        "conflict_scan": make_conflict_handler(session_factory, tables),
        "dedupe_claims": make_dedupe_handler(session_factory, tables),
        "daily_digest": digest,
    }


def build_job_recheck(session_factory: Any, tables: Mapping[str, sa.Table]):
    """Recheck client revocation, secret admission and target version at both fences."""
    observed_versions: dict[str, Any] = {}
    # Index jobs re-read the target row at execution time (SearchIndexer._raw_input
    # / _simple / _project), so a version change between fences is harmless: the
    # index always reflects the latest state. Exempt only the index_* family;
    # every other job keeps the original version fencing.
    VERSION_EXEMPT = frozenset({
        "index_raw_input", "index_todo", "index_self_claim",
        "index_project", "index_project_task", "index_checkpoint",
        "index_workspace_observation",
    })
    target_tables = {
        "raw_input": "raw_inputs", "todo": "todos", "self_claim": "self_claims",
        "project": "projects", "project_task": "project_tasks", "checkpoint": "checkpoints",
        "workspace_observation": "workspace_observations", "asset": "assets",
        "review_item": "review_inbox_items",
    }

    def recheck(job: dict[str, Any], phase: str) -> None:
        if detect_secret(filename="job-reference", content_type="text/plain",
                         content=str(job["payload_ref"])).matched:
            raise JobExecutionError("SECRET_REJECTED", retryable=False)
        with session_factory() as session:
            client_id = job.get("client_id")
            if client_id is not None:
                active = session.scalar(sa.select(tables["clients"].c.id).where(
                    tables["clients"].c.id == client_id,
                    tables["clients"].c.owner_id == job["owner_id"],
                    tables["clients"].c.status == "active",
                ))
                if active is None:
                    raise JobExecutionError("CLIENT_REVOKED", retryable=False)
            try:
                target_type, raw_id = job["payload_ref"].split(":", 1)
                target_id = UUID(raw_id)
            except (ValueError, AttributeError):
                return
            table_name = target_tables.get(target_type)
            if table_name is None or table_name not in tables:
                return
            table = tables[table_name]
            marker_column = table.c.get("version")
            if marker_column is None:
                marker_column = table.c.get("updated_at")
            if marker_column is None:
                return
            marker = session.scalar(sa.select(marker_column).where(
                table.c.id == target_id, table.c.owner_id == job["owner_id"],
            ))
            if marker is None:
                raise JobExecutionError("NOT_FOUND", retryable=False)
            key = str(job["id"])
            if phase == "before_execute":
                observed_versions[key] = marker
            elif (observed_versions.get(key) != marker
                  and job.get("job_type") not in VERSION_EXEMPT):
                raise JobExecutionError("VERSION_CONFLICT", retryable=False)

    return recheck
