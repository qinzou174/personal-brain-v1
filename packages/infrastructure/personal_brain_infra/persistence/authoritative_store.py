"""Owner-scoped authoritative persistence for canonical write paths.

This adapter intentionally reflects the migration-owned schema rather than
declaring a second ORM schema.  A write is acknowledged as
``canonical_committed`` only after its canonical row, source, idempotency
outcome, durable job and body-free audit event commit in one UnitOfWork.
"""

from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from personal_brain_domain.common.errors import BrainError
from personal_brain_infra.persistence.idempotency import claim_request, complete_claim
from personal_brain_infra.persistence.unit_of_work import UnitOfWork
from personal_brain_infra.storage.base import StorageBackend


_TABLES = (
    "owners",
    "clients",
    "intake_requests",
    "raw_inputs",
    "expenses",
    "idempotency_records",
    "jobs",
    "audit_events",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class AuthoritativeStore:
    """A durable, owner-bound repository over the migration-owned tables."""

    def __init__(self, session_factory: Any, *, owner_id: UUID, client_id: UUID) -> None:
        self._session_factory = session_factory
        self.owner_id = owner_id
        self.client_id = client_id
        metadata = sa.MetaData()
        with session_factory() as session:
            metadata.reflect(bind=session.get_bind())
        missing = set(_TABLES).difference(metadata.tables)
        if missing:
            raise RuntimeError(f"authoritative schema missing tables: {sorted(missing)}")
        self.tables = metadata.tables

    def _commit_record(
        self,
        *,
        operation: str,
        idempotency_key: UUID,
        source_text: str,
        requested_scope: str,
        tool: str,
        target_category: str,
        target_table: str | None,
        target_values: Callable[[UUID, UUID, datetime], dict[str, Any]] | None,
        result_key: str,
        job_type: str,
        extra_jobs: tuple[str, ...] = (),
        pre_commit: Callable[[], None] | None = None,
        side_effect: Callable[[Session, UUID, UUID, datetime], None] | None = None,
        existing_target_id: UUID | None = None,
        dedupe_digest: str | None = None,
    ) -> dict[str, Any]:
        if target_table is not None and target_table not in self.tables:
            raise RuntimeError(f"authoritative schema missing table: {target_table}")
        payload_digest = _digest({
            "operation": operation, "source_text": source_text, "scope": requested_scope,
        })
        now = _utcnow()
        intake_id, source_id, target_id = uuid4(), uuid4(), existing_target_id or uuid4()
        correlation_id, job_id, audit_id = uuid4(), uuid4(), uuid4()
        intake = self.tables["intake_requests"]
        raw = self.tables["raw_inputs"]
        jobs = self.tables["jobs"]
        audit = self.tables["audit_events"]
        idempotency = self.tables["idempotency_records"]
        with UnitOfWork(self._session_factory) as uow:
            session = uow.session
            self._assert_authority(session)
            claim = claim_request(
                session, idempotency, owner_id=self.owner_id, client_id=self.client_id,
                operation=operation, idempotency_key=idempotency_key, payload_digest=payload_digest,
            )
            if claim.state == "replay":
                return dict(claim.outcome or {})
            if claim.state == "deleted":
                return {"status": "deleted", "persistence": "tombstone"}
            if claim.state == "in_progress":
                raise BrainError("BRAIN_UNAVAILABLE")
            session.execute(intake.insert().values(
                id=self._db_id(intake, "id", intake_id),
                owner_id=self._db_id(intake, "owner_id", self.owner_id),
                client_id=self._db_id(intake, "client_id", self.client_id),
                operation=operation,
                idempotency_key=self._db_id(intake, "idempotency_key", idempotency_key),
                received_at=now, content_ref=None, detected_intent=operation,
                declared_intent=operation, requested_scope=requested_scope,
                security_decision="allow", intake_level="L1", state="processing",
                outcome_refs=[], correlation_id=self._db_id(intake, "correlation_id", correlation_id),
                error_code=None,
            ))
            content_digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
            if dedupe_digest is not None:
                # D3: the client explicitly asks for content-level duplicate
                # detection (a forked/regenerated conversation re-sends the same
                # entry). The claimed hash must equal the server's own digest, so
                # a client bug can never fold different content into one record.
                if dedupe_digest != content_digest:
                    raise BrainError("VALIDATION_FAILED")
                existing = session.execute(sa.select(
                    raw.c.id, raw.c.intake_request_id,
                ).where(
                    raw.c.owner_id == self._db_id(raw, "owner_id", self.owner_id),
                    raw.c.content_hash == content_digest,
                    raw.c.lifecycle_state == "active",
                ).limit(1)).mappings().first()
                if existing is not None:
                    # Native UUID, 32-hex and string-backed schemas all appear in
                    # practice, so normalize through one explicit boundary.
                    existing_id = UUID(str(existing["id"]))
                    outcome = {
                        "status": "duplicate", "persistence": "already_committed",
                        result_key: self._external_id(existing_id),
                        "source_id": self._external_id(existing_id),
                        "operation_id": self._external_id(existing["intake_request_id"]),
                        "duplicate_of": self._external_id(existing_id),
                    }
                    session.execute(
                        intake.update().where(intake.c.id == self._db_id(intake, "id", intake_id))
                        .values(state="completed", outcome_refs=[str(existing_id)])
                    )
                    session.execute(audit.insert().values(
                        id=self._db_id(audit, "id", audit_id),
                        owner_id=self._db_id(audit, "owner_id", self.owner_id),
                        client_id=self._db_id(audit, "client_id", self.client_id),
                        correlation_id=self._db_id(audit, "correlation_id", correlation_id),
                        action=operation, tool=tool, effective_scope=requested_scope,
                        target_category=target_category,
                        target_id=self._db_id(audit, "target_id", existing_id),
                        outcome="duplicate", error_code=None, duration_ms=0, occurred_at=now,
                        risk="ordinary", authorization_decision="allow",
                    ))
                    complete_claim(session, idempotency, claim_id=claim.id, outcome=outcome)
                    uow.commit()
                    return outcome
            session.execute(raw.insert().values(
                id=self._db_id(raw, "id", source_id),
                owner_id=self._db_id(raw, "owner_id", self.owner_id),
                intake_request_id=self._db_id(raw, "intake_request_id", intake_id),
                client_id=self._db_id(raw, "client_id", self.client_id),
                content_text=source_text, asset_ref=None,
                content_hash=content_digest,
                original_at=now, original_timezone="UTC", source_channel="api",
                language="zh-CN", retention_policy="canonical", sensitivity="normal",
                information_class="explicit_user_statement", canonicality="canonical",
                source_kind="explicit_user_statement", source_id=self._db_id(raw, "source_id", source_id),
                valid_from=now, valid_to=None, lifecycle_state="active", deleted_at=None,
            ))
            if target_table is not None and target_values is not None:
                table = self.tables[target_table]
                values = target_values(target_id, source_id, now)
                values["id"] = self._db_id(table, "id", target_id)
                values["owner_id"] = self._db_id(table, "owner_id", self.owner_id)
                if "source_id" in values:
                    values["source_id"] = self._db_id(table, "source_id", source_id)
                if "version" in table.c and "version" not in values:
                    values["version"] = 1
                session.execute(table.insert().values(**values))
            elif existing_target_id is None:
                target_id = source_id
            if side_effect is not None:
                side_effect(session, target_id, source_id, now)
            session.execute(jobs.insert().values(
                id=self._db_id(jobs, "id", job_id), owner_id=self._db_id(jobs, "owner_id", self.owner_id),
                client_id=self._db_id(jobs, "client_id", self.client_id), job_type=job_type,
                payload_ref=f"{target_category}:{target_id}",
                idempotency_key=self._db_id(jobs, "idempotency_key", idempotency_key),
                state="queued", priority=0, attempts=0, max_attempts=5, available_at=now, claim_token=0,
            ))
            # Additional intake-stage jobs (e.g. index + extract) commit in the
            # same UnitOfWork, so a canonical write never loses a pipeline stage.
            for extra_type in extra_jobs:
                session.execute(jobs.insert().values(
                    id=self._db_id(jobs, "id", uuid4()),
                    owner_id=self._db_id(jobs, "owner_id", self.owner_id),
                    client_id=self._db_id(jobs, "client_id", self.client_id),
                    job_type=extra_type, payload_ref=f"{target_category}:{target_id}",
                    idempotency_key=self._db_id(jobs, "idempotency_key", idempotency_key),
                    state="queued", priority=0, attempts=0, max_attempts=5,
                    available_at=now, claim_token=0,
                ))
            session.execute(audit.insert().values(
                id=self._db_id(audit, "id", audit_id), owner_id=self._db_id(audit, "owner_id", self.owner_id),
                client_id=self._db_id(audit, "client_id", self.client_id),
                correlation_id=self._db_id(audit, "correlation_id", correlation_id),
                action=operation, tool=tool, effective_scope=requested_scope,
                target_category=target_category, target_id=self._db_id(audit, "target_id", target_id),
                outcome="completed", error_code=None, duration_ms=0, occurred_at=now,
                risk="ordinary", authorization_decision="allow",
            ))
            outcome = {
                "status": "accepted", "persistence": "canonical_committed",
                result_key: str(target_id), "source_id": str(source_id), "operation_id": str(intake_id),
            }
            session.execute(
                intake.update().where(intake.c.id == self._db_id(intake, "id", intake_id))
                .values(state="completed", outcome_refs=[str(target_id), str(source_id)])
            )
            complete_claim(session, idempotency, claim_id=claim.id, outcome=outcome)
            if pre_commit is not None:
                pre_commit()
            uow.commit()
        return outcome

    def save_note(
        self, *, content: str, requested_scope: str, idempotency_key: UUID,
        pre_commit: Callable[[], None] | None = None, content_hash: str | None = None,
    ) -> dict[str, Any]:
        """Two intake stages: retrieval projection (index) plus LLM extraction.

        ``content_hash`` (optional) opts into content-level duplicate detection:
        a forked conversation that re-sends an identical entry returns the record
        that already exists instead of a second canonical row (status
        ``duplicate``). The claimed hash must match the server's own digest.
        """
        return self._commit_record(
            operation="save_note", idempotency_key=idempotency_key, source_text=content,
            requested_scope=requested_scope, tool="knowledge.write", target_category="raw_input",
            target_table=None, target_values=None, result_key="record_id",
            job_type="index_raw_input", extra_jobs=("extract_raw_input",), pre_commit=pre_commit,
            dedupe_digest=content_hash.strip().lower() if content_hash else None,
        )

    def add_todo(
        self, *, content: str, requested_scope: str, idempotency_key: UUID,
        priority: int = 0, pre_commit: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        return self._commit_record(
            operation="add_todo", idempotency_key=idempotency_key, source_text=content,
            requested_scope=requested_scope, tool="todo.write", target_category="todo",
            target_table="todos", result_key="todo_id", job_type="index_todo", pre_commit=pre_commit,
            target_values=lambda _target, source, now: {
                "content": content, "state": "pending", "due_at": None, "due_timezone": None,
                "due_window_start": None, "due_window_end": None, "due_precision": None,
                "priority": priority, "completed_at": None, "archived_at": None,
                "source_id": source, "sensitivity": "normal",
                "information_class": "explicit_user_statement", "canonicality": "canonical",
                "source_kind": "explicit_user_statement", "valid_from": now, "valid_to": None,
                "lifecycle_state": "active", "deleted_at": None,
            },
        )

    def create_project(
        self, *, name: str, purpose: str, requested_scope: str, idempotency_key: UUID,
        pre_commit: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        return self._commit_record(
            operation="create_project", idempotency_key=idempotency_key,
            source_text=f"{name}\n{purpose}", requested_scope=requested_scope,
            tool="project.write", target_category="project", target_table="projects",
            result_key="project_id", job_type="bootstrap_project",
            target_values=lambda _target, _source, _now: {
                "name": name, "purpose": purpose, "goals": [], "principles": [],
                "technology_summary": None, "architecture_summary": None,
                "deployment_summary": None, "global_constraints": [],
                "directory_overview": None, "workspace_identity": None,
                "repository_identity": None, "current_revision_evidence": {},
                "lifecycle_state": "active",
            },
            pre_commit=pre_commit,
        )

    def propose_self_claim(
        self, *, category: str, claim_text: str, policy_class: str,
        requested_scope: str, idempotency_key: UUID, pre_commit: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        review = "pending_confirmation" if policy_class == "C" else "none"
        lifecycle = "candidate"
        return self._commit_record(
            operation="propose_self_claim", idempotency_key=idempotency_key,
            source_text=claim_text, requested_scope=requested_scope, tool="self.write",
            target_category="self_claim", target_table="self_claims", result_key="claim_id",
            job_type="index_self_claim",
            target_values=lambda _target, source, now: {
                "category": category, "claim": claim_text, "policy_class": policy_class,
                "lifecycle_state": lifecycle, "establishment": "explicit",
                "review": review, "correction_events": [], "confidence_inputs": {},
                "evidence_summary": [], "valid_from": now, "valid_to": None,
                "context": requested_scope, "exceptions": [], "confirmation_identity": None,
                "confirmation_time": None, "source_id": source,
            },
            pre_commit=pre_commit,
        )

    def create_review_item(
        self, *, item_type: str, subject_refs: list[str], proposal: dict[str, Any],
        requested_scope: str, idempotency_key: UUID, pre_commit: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        return self._commit_record(
            operation="create_review_item", idempotency_key=idempotency_key,
            source_text=json.dumps(proposal, sort_keys=True, ensure_ascii=False),
            requested_scope=requested_scope, tool="review.write", target_category="review_item",
            target_table="review_inbox_items", result_key="review_item_id", job_type="notify_review",
            target_values=lambda _target, _source, _now: {
                "item_type": item_type, "subject_refs": subject_refs, "proposal": proposal,
                "risk": "ordinary", "evidence": [], "state": "open", "resolver_id": None,
                "resolved_at": None,
                "expires_at": _now + timedelta(minutes=15) if item_type in {
                    "profile_confirmation", "deletion_confirmation", "permission_change",
                } else None,
                "expected_version": 1,
            },
            pre_commit=pre_commit,
        )

    def create_deletion_plan(
        self, *, targets: list[tuple[str, UUID]], dependents: dict[UUID, list[tuple[str, UUID]]],
        requested_scope: str, idempotency_key: UUID, pre_commit: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        """Persist a preview-only deletion plan and an owner review confirmation.

        FR-079/FR-080/ER-09: nothing is hidden or purged before confirmation; the
        plan records every dependent's proposed action so approval can execute the
        dependency plan across originals/derived/indexes/relations/evidence/caches.
        """
        required = {"deletion_plans", "deletion_actions", "review_inbox_items"}
        if not required <= set(self.tables):
            raise RuntimeError(f"governed deletion schema missing tables: {sorted(required - set(self.tables))}")
        plans, items, jobs, audit, idempotency, intake = (
            self.tables["deletion_plans"], self.tables["review_inbox_items"], self.tables["jobs"],
            self.tables["audit_events"], self.tables["idempotency_records"], self.tables["intake_requests"],
        )
        now, plan_id, item_id, job_id, audit_id, correlation_id = _utcnow(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        # A project owns its facts. Decisions/constraints/change events travel
        # with it even when the caller did not enumerate them — otherwise the
        # approved plan would leave a deleted project's facts active and indexed.
        resolved = {target_id: list(dependents.get(target_id, [])) for _type, target_id in targets}
        with self._session_factory() as session:
            for target_type, target_id in targets:
                if target_type != "project":
                    continue
                for fact_type, table_name in (("decision", "decisions"),
                                              ("constraint", "constraints"),
                                              ("change_event", "change_events")):
                    table = self.tables.get(table_name)
                    if table is None:
                        continue
                    fact_ids = session.scalars(sa.select(table.c.id).where(
                        table.c.owner_id == self._db_id(table, "owner_id", self.owner_id),
                        table.c.project_id == self._db_id(table, "project_id", target_id),
                        table.c.lifecycle_state == "active",
                    ))
                    declared = resolved[target_id]
                    for fact_id in fact_ids:
                        entry = (fact_type, UUID(self._external_id(fact_id)))
                        if entry not in declared:
                            declared.append(entry)
                # Tasks and their checkpoints carry no lifecycle_state of their
                # own, so only the plan can clear their retrieval cards: discover
                # them under the project instead of relying on the caller.
                tasks_table = self.tables.get("project_tasks")
                if tasks_table is None:
                    continue
                task_ids = list(session.scalars(sa.select(tasks_table.c.id).where(
                    tasks_table.c.owner_id == self._db_id(tasks_table, "owner_id", self.owner_id),
                    tasks_table.c.project_id == self._db_id(tasks_table, "project_id", target_id),
                )))
                for task_id in task_ids:
                    entry = ("project_task", UUID(self._external_id(task_id)))
                    if entry not in declared:
                        declared.append(entry)
                checkpoints_table = self.tables.get("checkpoints")
                if task_ids and checkpoints_table is not None:
                    checkpoint_ids = session.scalars(sa.select(checkpoints_table.c.id).where(
                        checkpoints_table.c.owner_id == self._db_id(
                            checkpoints_table, "owner_id", self.owner_id,
                        ),
                        checkpoints_table.c.task_id.in_(task_ids),
                    ))
                    for checkpoint_id in checkpoint_ids:
                        entry = ("checkpoint", UUID(self._external_id(checkpoint_id)))
                        if entry not in declared:
                            declared.append(entry)
        impact_graph = {str(target_id): [
            {"target_type": dep_type, "target_id": str(dep_id)}
            for dep_type, dep_id in resolved.get(target_id, [])
        ] for _, target_id in targets}
        payload = {"targets": [[t, str(i)] for t, i in targets], "impact": impact_graph}
        with UnitOfWork(self._session_factory) as uow:
            session = uow.session
            self._assert_authority(session)
            claim = claim_request(
                session, idempotency, owner_id=self.owner_id, client_id=self.client_id,
                operation="create_deletion_plan", idempotency_key=idempotency_key,
                payload_digest=_digest(payload),
            )
            if claim.state == "replay":
                return dict(claim.outcome or {})
            if claim.state != "created":
                raise BrainError("BRAIN_UNAVAILABLE")
            session.execute(intake.insert().values(
                id=self._db_id(intake, "id", uuid4()),
                owner_id=self._db_id(intake, "owner_id", self.owner_id),
                client_id=self._db_id(intake, "client_id", self.client_id),
                operation="create_deletion_plan",
                idempotency_key=self._db_id(intake, "idempotency_key", idempotency_key),
                received_at=now, content_ref=None, detected_intent="deletion.plan",
                declared_intent="deletion.plan", requested_scope=requested_scope,
                security_decision="allow", intake_level="L1", state="completed", outcome_refs=[str(plan_id)],
                correlation_id=self._db_id(intake, "correlation_id", correlation_id), error_code=None,
            ))
            session.execute(plans.insert().values(
                id=self._db_id(plans, "id", plan_id),
                owner_id=self._db_id(plans, "owner_id", self.owner_id),
                requested_targets=[[t, str(i)] for t, i in targets],
                impact_graph=impact_graph, policy_actions=impact_graph,
                backup_implications={"production_purged": True, "backup_purge_due": True},
                risk="high", confirmation_state="pending", confirmation_identity=None,
                confirmation_time=None, execution_state="preview", reconciliation_state="pending",
                audit_ref=None,
            ))
            session.execute(items.insert().values(
                id=self._db_id(items, "id", item_id),
                owner_id=self._db_id(items, "owner_id", self.owner_id),
                item_type="deletion_confirmation",
                subject_refs=[str(i) for _, i in targets],
                proposal={"plan_id": str(plan_id), "impact": impact_graph, "scope": requested_scope},
                risk="high", evidence=[], state="open", resolver_id=None, resolved_at=None,
                expires_at=now + timedelta(minutes=15), expected_version=1,
            ))
            session.execute(jobs.insert().values(
                id=self._db_id(jobs, "id", job_id),
                owner_id=self._db_id(jobs, "owner_id", self.owner_id),
                client_id=self._db_id(jobs, "client_id", self.client_id),
                job_type="notify_review", payload_ref=f"review_item:{item_id}",
                idempotency_key=self._db_id(jobs, "idempotency_key", idempotency_key),
                state="queued", priority=0, attempts=0, max_attempts=5, available_at=now, claim_token=0,
            ))
            session.execute(audit.insert().values(
                id=self._db_id(audit, "id", audit_id),
                owner_id=self._db_id(audit, "owner_id", self.owner_id),
                client_id=self._db_id(audit, "client_id", self.client_id),
                correlation_id=self._db_id(audit, "correlation_id", correlation_id),
                action="create_deletion_plan", tool="review.write", effective_scope=requested_scope,
                target_category="deletion_plan", target_id=self._db_id(audit, "target_id", plan_id),
                outcome="completed", error_code=None, duration_ms=0, occurred_at=now,
                risk="high", authorization_decision="allow",
            ))
            outcome = {
                "status": "accepted", "persistence": "canonical_committed",
                "plan_id": str(plan_id), "review_item_id": str(item_id),
                "execution_state": "preview", "confirmation_state": "pending",
            }
            complete_claim(session, idempotency, claim_id=claim.id, outcome=outcome)
            if pre_commit is not None:
                pre_commit()
            uow.commit()
        return outcome

    def get_deletion_plan(self, plan_id: UUID) -> dict[str, Any]:
        plans, items = self.tables["deletion_plans"], self.tables["review_inbox_items"]
        with self._session_factory() as session:
            self._assert_authority(session)
            row = session.execute(sa.select(plans).where(
                plans.c.id == self._db_id(plans, "id", plan_id),
                plans.c.owner_id == self._db_id(plans, "owner_id", self.owner_id),
            )).mappings().one_or_none()
            if row is None:
                raise BrainError("NOT_FOUND")
            reviews = session.execute(sa.select(items).where(
                items.c.owner_id == self._db_id(items, "owner_id", self.owner_id),
                items.c.item_type == "deletion_confirmation",
                items.c.state == "open",
            )).mappings().all()
        return {
            "plan_id": self._external_id(row["id"]),
            "requested_targets": list(row["requested_targets"]),
            "impact_graph": dict(row["impact_graph"] or {}),
            "policy_actions": dict(row["policy_actions"] or {}),
            "risk": row["risk"], "execution_state": row["execution_state"],
            "confirmation_state": row["confirmation_state"],
            "reconciliation_state": row["reconciliation_state"],
            "review_item_id": self._external_id(reviews[0]["id"]) if reviews else None,
        }

    def persist_conflict(
        self, *, participants: list[str], conflict_type: str, state: str,
        idempotency_key: UUID, requested_scope: str, pre_commit: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        """Persist a resolved conflict record without silently dropping participants."""
        if "conflicts" not in self.tables:
            raise RuntimeError("governed deletion schema missing conflicts table")
        conflicts, audit, idempotency = (
            self.tables["conflicts"], self.tables["audit_events"], self.tables["idempotency_records"],
        )
        now, conflict_id, correlation_id = _utcnow(), uuid4(), uuid4()
        with UnitOfWork(self._session_factory) as uow:
            session = uow.session
            self._assert_authority(session)
            claim = claim_request(
                session, idempotency, owner_id=self.owner_id, client_id=self.client_id,
                operation="persist_conflict", idempotency_key=idempotency_key,
                payload_digest=_digest({"participants": participants, "state": state}),
            )
            if claim.state == "replay":
                return dict(claim.outcome or {})
            if claim.state != "created":
                raise BrainError("BRAIN_UNAVAILABLE")
            session.execute(conflicts.insert().values(
                id=self._db_id(conflicts, "id", conflict_id),
                owner_id=self._db_id(conflicts, "owner_id", self.owner_id),
                participants=list(participants), conflict_type=conflict_type,
                detected_at=now, evidence=[], state=state, resolution=None, resolver=None,
            ))
            session.execute(audit.insert().values(
                id=self._db_id(audit, "id", uuid4()),
                owner_id=self._db_id(audit, "owner_id", self.owner_id),
                client_id=self._db_id(audit, "client_id", self.client_id),
                correlation_id=self._db_id(audit, "correlation_id", correlation_id),
                action="persist_conflict", tool="review.write", effective_scope=requested_scope,
                target_category="conflict", target_id=self._db_id(audit, "target_id", conflict_id),
                outcome="completed", error_code=None, duration_ms=0, occurred_at=now,
                risk="ordinary", authorization_decision="allow",
            ))
            outcome = {"status": "completed", "persistence": "canonical_committed",
                       "conflict_id": str(conflict_id)}
            complete_claim(session, idempotency, claim_id=claim.id, outcome=outcome)
            if pre_commit is not None:
                pre_commit()
            uow.commit()
        return outcome

    def list_conflicts(self) -> list[dict[str, Any]]:
        conflicts = self.tables["conflicts"]
        with self._session_factory() as session:
            self._assert_authority(session)
            rows = session.execute(sa.select(conflicts).where(
                conflicts.c.owner_id == self._db_id(conflicts, "owner_id", self.owner_id),
            ).order_by(conflicts.c.detected_at)).mappings().all()
        return [{
            "conflict_id": self._external_id(row["id"]),
            "conflict_type": row["conflict_type"], "state": row["state"],
            "participants": list(row["participants"] or []),
        } for row in rows]

    def persist_retention(
        self, *, target_type: str, target_id: UUID, action: str,
        idempotency_key: UUID, requested_scope: str, pre_commit: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        """Record a retention application outcome (archive/expire/historical)."""
        audit, idempotency = self.tables["audit_events"], self.tables["idempotency_records"]
        now, correlation_id = _utcnow(), uuid4()
        with UnitOfWork(self._session_factory) as uow:
            session = uow.session
            self._assert_authority(session)
            claim = claim_request(
                session, idempotency, owner_id=self.owner_id, client_id=self.client_id,
                operation="persist_retention", idempotency_key=idempotency_key,
                payload_digest=_digest({"target_type": target_type, "action": action}),
            )
            if claim.state == "replay":
                return dict(claim.outcome or {})
            if claim.state != "created":
                raise BrainError("BRAIN_UNAVAILABLE")
            session.execute(audit.insert().values(
                id=self._db_id(audit, "id", uuid4()),
                owner_id=self._db_id(audit, "owner_id", self.owner_id),
                client_id=self._db_id(audit, "client_id", self.client_id),
                correlation_id=self._db_id(audit, "correlation_id", correlation_id),
                action="persist_retention", tool="review.write", effective_scope=requested_scope,
                target_category=target_type, target_id=self._db_id(audit, "target_id", target_id),
                outcome=action, error_code=None, duration_ms=0, occurred_at=now,
                risk="ordinary", authorization_decision="allow",
            ))
            outcome = {"status": "completed", "persistence": "canonical_committed", "action": action}
            complete_claim(session, idempotency, claim_id=claim.id, outcome=outcome)
            if pre_commit is not None:
                pre_commit()
            uow.commit()
        return outcome

    def _execute_approved_deletion_plan(self, session: Session, *, plan_id: UUID,
                                        requested_scope: str, now: datetime) -> None:
        """Execute the dependency plan after owner confirmation.

        Writes one value-free deletion_action per target and dependent, tombstones
        the original, marks affected evidence as recomputing, enqueues the fenced
        reconcile_deletion job and records a body-free audit outcome (ER-09).
        """
        plans, actions, jobs, audit = (
            self.tables["deletion_plans"], self.tables["deletion_actions"],
            self.tables["jobs"], self.tables["audit_events"],
        )
        plan_row = session.execute(sa.select(plans).where(
            plans.c.id == self._db_id(plans, "id", plan_id),
            plans.c.owner_id == self._db_id(plans, "owner_id", self.owner_id),
            plans.c.execution_state == "preview",
        ).with_for_update()).mappings().one_or_none()
        if plan_row is None:
            raise BrainError("VERSION_CONFLICT")
        requested = [tuple(item) for item in (plan_row["requested_targets"] or [])]
        impact = dict(plan_row["impact_graph"] or {})
        canonical_targets = {str(target_id) for target_type, target_id in requested}
        plan_key = self._db_id(plans, "id", plan_id)
        opaque_version = _utcnow().timestamp()  # monotonic opaque deletion version
        deletion_actions: list[tuple[str, UUID, str]] = []
        for target_type, raw_target in requested:
            target_id = UUID(str(raw_target))
            ttype = target_type
            deletion_actions.append((ttype, target_id, "delete"))
            for dep in impact.get(str(target_id), []):
                deletion_actions.append((dep["target_type"], UUID(str(dep["target_id"])), "recompute"
                                         if dep["target_type"] == "evidence" else "delete"))
        for ttype, target_id, action in deletion_actions:
            action_key = self._db_id(actions, "id", uuid4())
            session.execute(actions.insert().values(
                id=action_key, owner_id=self._db_id(actions, "owner_id", self.owner_id),
                plan_id=plan_key, target_type=ttype,
                target_id=self._db_id(actions, "target_id", target_id),
                action=action, produced_purged=True, backup_purge_due=True,
                performed_at=now, opaque_deletion_version=int(opaque_version),
            ))
        # Tombstone canonical originals and their raw sources (value-free).
        # Project facts (decision/constraint/change_event) are declared as
        # dependents of their project, so they must tombstone with it — leaving
        # them active would keep a deleted project's facts readable (and
        # re-indexable by a later refresh job).
        table_for = {
            "raw_input": "raw_inputs", "expense": "expenses", "todo": "todos",
            "self_claim": "self_claims", "document": "documents", "asset": "assets",
            "project": "projects", "project_task": "project_tasks",
            "decision": "decisions", "constraint": "constraints",
            "change_event": "change_events",
        }
        raw_inputs = self.tables.get("raw_inputs")
        for ttype, target_id, _action in deletion_actions:
            table_name = table_for.get(ttype)
            if table_name not in self.tables:
                continue
            table = self.tables[table_name]
            if "lifecycle_state" not in table.c:
                continue
            # Not every canonical table carries deleted_at (e.g. projects);
            # tombstone with the columns the table actually declares.
            tombstone = {"lifecycle_state": "deleted", "updated_at": now}
            if "deleted_at" in table.c:
                tombstone["deleted_at"] = now
            session.execute(table.update().where(
                table.c.id == self._db_id(table, "id", target_id),
                table.c.owner_id == self._db_id(table, "owner_id", self.owner_id),
            ).values(**tombstone))
            # The immutable raw source of a deleted canonical target is also
            # retired so late retries cannot restore deleted body references.
            if raw_inputs is not None and "source_id" in table.c and ttype not in {"raw_input"}:
                try:
                    source_ref = session.execute(sa.select(table.c.source_id).where(
                        table.c.id == self._db_id(table, "id", target_id),
                    )).scalar_one_or_none()
                except sa.exc.SQLAlchemyError:
                    source_ref = None
                if "lifecycle_state" in raw_inputs.c:
                    if source_ref is not None:
                        session.execute(raw_inputs.update().where(
                            raw_inputs.c.id == source_ref,
                            raw_inputs.c.owner_id == self._db_id(raw_inputs, "owner_id", self.owner_id),
                        ).values(lifecycle_state="deleted", deleted_at=now, updated_at=now))
                    # Capture-source records that share the target identity.
                    session.execute(raw_inputs.update().where(
                        raw_inputs.c.id == self._db_id(raw_inputs, "id", target_id),
                        raw_inputs.c.owner_id == self._db_id(raw_inputs, "owner_id", self.owner_id),
                    ).values(lifecycle_state="deleted", deleted_at=now, updated_at=now))
        # Recalculate evidence whose source was deleted.
        if "evidence" in self.tables:
            evidence = self.tables["evidence"]
            session.execute(evidence.update().where(
                evidence.c.owner_id == self._db_id(evidence, "owner_id", self.owner_id),
                sa.or_(
                    sa.and_(evidence.c.source_type.in_(("expense", "raw_input", "document", "asset")),
                            evidence.c.source_id.in_(
                                [self._db_id(evidence, "source_id", target_id)
                                 for _t, target_id, _a in deletion_actions]),
                            evidence.c.lifecycle_state == "active"),
                    evidence.c.target_id.in_(canonical_targets),
                ),
            ).values(lifecycle_state="recomputing", updated_at=now))
        # Enqueue fenced reconciliation job.
        job_id, correlation_id = uuid4(), uuid4()
        session.execute(jobs.insert().values(
            id=self._db_id(jobs, "id", job_id),
            owner_id=self._db_id(jobs, "owner_id", self.owner_id),
            client_id=self._db_id(jobs, "client_id", self.client_id),
            job_type="reconcile_deletion", payload_ref=f"deletion_plan:{plan_id}",
            idempotency_key=self._db_id(jobs, "idempotency_key", uuid4()),
            state="queued", priority=0, attempts=0, max_attempts=5, available_at=now, claim_token=0,
        ))
        session.execute(audit.insert().values(
            id=self._db_id(audit, "id", uuid4()),
            owner_id=self._db_id(audit, "owner_id", self.owner_id),
            client_id=self._db_id(audit, "client_id", self.client_id),
            correlation_id=self._db_id(audit, "correlation_id", correlation_id),
            action="execute_deletion_plan", tool="review.write", effective_scope=requested_scope,
            target_category="deletion_plan", target_id=self._db_id(audit, "target_id", plan_id),
            outcome="approved", error_code=None, duration_ms=0, occurred_at=now,
            risk="high", authorization_decision="allow",
        ))
        session.execute(plans.update().where(plans.c.id == plan_key).values(
            confirmation_state="confirmed",
            confirmation_identity=str(self.owner_id),
            confirmation_time=now, execution_state="completed",
            reconciliation_state="queued", updated_at=now,
        ))

    def list_review_items(self, *, state: str = "open") -> list[dict[str, Any]]:
        items = self.tables["review_inbox_items"]
        with self._session_factory() as session:
            self._assert_authority(session)
            rows = session.execute(sa.select(items).where(
                items.c.owner_id == self._db_id(items, "owner_id", self.owner_id),
                items.c.state == state,
            ).order_by(items.c.created_at, items.c.id)).mappings().all()
        return [{
            "review_item_id": self._external_id(row["id"]), "item_type": row["item_type"],
            "subject_refs": list(row["subject_refs"]), "proposal": dict(row["proposal"]),
            "risk": row["risk"], "state": row["state"], "version": row["expected_version"],
            "expires_at": None if row["expires_at"] is None else row["expires_at"].isoformat(),
        } for row in rows]

    def resolve_review_item(
        self, *, item_id: UUID, expected_version: int, decision: str,
        idempotency_key: UUID, pre_commit: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        if decision not in {"approved", "rejected"}:
            raise BrainError("VALIDATION_FAILED")
        items, claims, audit = (
            self.tables["review_inbox_items"], self.tables["idempotency_records"],
            self.tables["audit_events"],
        )
        now, audit_id, correlation_id = _utcnow(), uuid4(), uuid4()
        digest = _digest({"item_id": str(item_id), "version": expected_version, "decision": decision})
        with UnitOfWork(self._session_factory) as uow:
            session = uow.session
            self._assert_authority(session)
            claim = claim_request(
                session, claims, owner_id=self.owner_id, client_id=self.client_id,
                operation="resolve_review_item", idempotency_key=idempotency_key,
                payload_digest=digest,
            )
            if claim.state == "replay":
                return dict(claim.outcome or {})
            if claim.state != "created":
                raise BrainError("BRAIN_UNAVAILABLE")
            row = session.execute(sa.select(items).where(
                items.c.id == self._db_id(items, "id", item_id),
                items.c.owner_id == self._db_id(items, "owner_id", self.owner_id),
            ).with_for_update()).mappings().one_or_none()
            if row is None:
                raise BrainError("NOT_FOUND")
            expires_at = row["expires_at"]
            if expires_at is not None:
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if now >= expires_at:
                    raise BrainError("CONFIRMATION_EXPIRED")
            if row["state"] != "open":
                raise BrainError("CONFIRMATION_REQUIRED")
            if int(row["expected_version"]) != expected_version:
                raise BrainError("VERSION_CONFLICT")
            session.execute(items.update().where(
                items.c.id == row["id"], items.c.state == "open",
                items.c.expected_version == expected_version,
            ).values(
                state=decision, resolver_id=self._db_id(items, "resolver_id", self.client_id),
                resolved_at=now, updated_at=now,
            ))
            merged_claims: list[str] = []
            if decision == "approved" and row["item_type"] == "profile_confirmation":
                claims_table = self.tables["self_claims"]
                for subject in row["subject_refs"]:
                    try:
                        subject_id = UUID(str(subject))
                    except ValueError:
                        continue
                    session.execute(claims_table.update().where(
                        claims_table.c.id == self._db_id(claims_table, "id", subject_id),
                        claims_table.c.owner_id == self._db_id(claims_table, "owner_id", self.owner_id),
                        claims_table.c.lifecycle_state == "candidate",
                        claims_table.c.review == "pending_confirmation",
                    ).values(
                        lifecycle_state="active", review="none",
                        confirmation_identity=str(self.owner_id), confirmation_time=now,
                        updated_at=now,
                    ))
            elif decision == "approved" and row["item_type"] == "deletion_confirmation":
                plan_id = UUID(str(row["proposal"].get("plan_id")))
                requested_scope = str(row["proposal"].get("scope") or "review")
                self._execute_approved_deletion_plan(
                    session, plan_id=plan_id, requested_scope=requested_scope, now=now,
                )
            elif decision == "approved" and row["item_type"] == "merge_candidate":
                # D2: an owner-approved duplicate merge is the claim merge/park
                # interface — evidence moves, duplicates are superseded with a
                # correction event, nothing is deleted.
                merged_claims = self._merge_claims(
                    session, subject_refs=list(row["subject_refs"] or []),
                    proposal=dict(row["proposal"] or {}),
                    review_item_id=row["id"], now=now,
                )
            elif decision == "rejected" and row["item_type"] == "deletion_confirmation" and "deletion_plans" in self.tables:
                try:
                    plan_id = UUID(str(row["proposal"].get("plan_id")))
                except (ValueError, TypeError):
                    plan_id = None
                if plan_id is not None:
                    session.execute(self.tables["deletion_plans"].update().where(
                        self.tables["deletion_plans"].c.id == self._db_id(
                            self.tables["deletion_plans"], "id", plan_id,
                        ),
                        self.tables["deletion_plans"].c.owner_id == self._db_id(
                            self.tables["deletion_plans"], "owner_id", self.owner_id,
                        ),
                        self.tables["deletion_plans"].c.confirmation_state == "pending",
                    ).values(
                        confirmation_state="rejected", updated_at=now,
                    ))
            session.execute(audit.insert().values(
                id=self._db_id(audit, "id", audit_id),
                owner_id=self._db_id(audit, "owner_id", self.owner_id),
                client_id=self._db_id(audit, "client_id", self.client_id),
                correlation_id=self._db_id(audit, "correlation_id", correlation_id),
                action="resolve_review_item", tool="review.write", effective_scope="review",
                target_category="review_item", target_id=self._db_id(audit, "target_id", item_id),
                outcome=decision, error_code=None, duration_ms=0, occurred_at=now,
                risk="high", authorization_decision="allow",
            ))
            outcome = {
                "status": "completed", "persistence": "canonical_committed",
                "review_item_id": str(item_id), "decision": decision,
            }
            if merged_claims:
                outcome["merged_claims"] = merged_claims
            complete_claim(session, claims, claim_id=claim.id, outcome=outcome)
            if pre_commit is not None:
                pre_commit()
            uow.commit()
        return outcome

    def _merge_claims(
        self, session: Session, *, subject_refs: list[Any], proposal: dict[str, Any],
        review_item_id: Any, now: datetime,
    ) -> list[str]:
        """Merge owner-approved duplicate claims inside the resolving transaction.

        Mirrors the worker's duplicate rule: the surviving row keeps the claim and
        absorbs the duplicate's evidence; every duplicate is superseded (never
        deleted) with a correction event, and its retrieval card stops being
        served. The caller persists the audit and the review outcome.
        """
        claims_table = self.tables["self_claims"]
        evidence_table = self.tables["evidence"]
        index_table = self.tables.get("search_index_entries")
        refs: list[UUID] = []
        for ref in subject_refs:
            try:
                refs.append(UUID(str(ref)))
            except (ValueError, TypeError):
                continue
        if len(refs) < 2:
            raise BrainError("VALIDATION_FAILED")
        rows = session.execute(sa.select(claims_table).where(
            claims_table.c.id.in_([self._db_id(claims_table, "id", ref) for ref in refs]),
            claims_table.c.owner_id == self._db_id(claims_table, "owner_id", self.owner_id),
            claims_table.c.lifecycle_state.in_(("candidate", "active", "historical")),
        )).mappings().all()
        if len(rows) < 2:
            return []
        survivor_id = None
        try:
            survivor_id = UUID(str(proposal.get("survivor_id")))
        except (ValueError, TypeError):
            survivor_id = None
        if survivor_id not in {row["id"] for row in rows}:
            survivor_id = sorted(rows, key=lambda row: (row["created_at"], str(row["id"])))[0]["id"]
        merged_ids = [row["id"] for row in rows if row["id"] != survivor_id]
        for merged_id in merged_ids:
            session.execute(evidence_table.update().where(
                evidence_table.c.owner_id == self._db_id(evidence_table, "owner_id", self.owner_id),
                evidence_table.c.target_type == "self_claim",
                evidence_table.c.target_id == self._db_id(evidence_table, "target_id", merged_id),
            ).values(
                target_id=self._db_id(evidence_table, "target_id", survivor_id),
                version=evidence_table.c.version + 1, updated_at=now,
            ))
            duplicate = session.execute(sa.select(claims_table).where(
                claims_table.c.id == self._db_id(claims_table, "id", merged_id),
            )).mappings().one()
            events = [dict(event) for event in (duplicate["correction_events"] or [])]
            events.append({"type": "superseded_by_duplicate_merge", "at": now.isoformat(),
                           "survivor_id": str(survivor_id),
                           "rule": "owner_approved_merge_candidate"})
            session.execute(claims_table.update().where(
                claims_table.c.id == self._db_id(claims_table, "id", merged_id),
            ).values(
                lifecycle_state="superseded", valid_to=now, correction_events=events, updated_at=now,
            ))
            if index_table is not None:
                session.execute(index_table.delete().where(
                    index_table.c.owner_id == self._db_id(index_table, "owner_id", self.owner_id),
                    index_table.c.target_type == "self_claim",
                    index_table.c.target_id == self._db_id(index_table, "target_id", merged_id),
                ))
        survivor = session.execute(sa.select(claims_table).where(
            claims_table.c.id == self._db_id(claims_table, "id", survivor_id),
        )).mappings().one()
        events = [dict(event) for event in (survivor["correction_events"] or [])]
        events.append({"type": "merged_duplicates", "at": now.isoformat(),
                       "merged_claim_ids": [str(merged_id) for merged_id in merged_ids],
                       "review_item_id": str(review_item_id),
                       "rule": "owner_approved_merge_candidate"})
        session.execute(claims_table.update().where(
            claims_table.c.id == self._db_id(claims_table, "id", survivor_id),
        ).values(correction_events=events, updated_at=now))
        return [str(merged_id) for merged_id in merged_ids]

    def get_operation_status(self, operation_id: UUID) -> dict[str, Any]:
        intake = self.tables["intake_requests"]
        with self._session_factory() as session:
            self._assert_authority(session)
            row = session.execute(sa.select(intake).where(
                intake.c.id == self._db_id(intake, "id", operation_id),
                intake.c.owner_id == self._db_id(intake, "owner_id", self.owner_id),
            )).mappings().one_or_none()
        if row is None:
            raise BrainError("NOT_FOUND")
        return {
            "operation_id": self._external_id(row["id"]), "operation": row["operation"],
            "status": row["state"], "result_refs": list(row["outcome_refs"]),
            "error_code": row["error_code"],
        }

    def list_todos(self) -> list[dict[str, Any]]:
        todos = self.tables["todos"]
        with self._session_factory() as session:
            self._assert_authority(session)
            rows = session.execute(sa.select(todos).where(
                todos.c.owner_id == self._db_id(todos, "owner_id", self.owner_id),
                todos.c.lifecycle_state == "active",
            ).order_by(todos.c.created_at, todos.c.id)).mappings().all()
        return [{
            "todo_id": self._external_id(row["id"]), "content": row["content"],
            "state": row["state"], "priority": row["priority"], "version": row["version"],
        } for row in rows]

    def complete_todo(
        self, *, todo_id: UUID, expected_version: int, idempotency_key: UUID,
        pre_commit: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        todos = self.tables["todos"]

        def transition(session: Session, _target: UUID, _source: UUID, now: datetime) -> None:
            row = session.execute(sa.select(todos).where(
                todos.c.id == self._db_id(todos, "id", todo_id),
                todos.c.owner_id == self._db_id(todos, "owner_id", self.owner_id),
            )).mappings().one_or_none()
            if row is None:
                raise BrainError("NOT_FOUND")
            if int(row["version"]) != expected_version or row["state"] not in {"pending", "in_progress"}:
                raise BrainError("VERSION_CONFLICT")
            session.execute(todos.update().where(
                todos.c.id == row["id"], todos.c.version == expected_version,
            ).values(state="completed", completed_at=now, archived_at=now,
                     version=expected_version + 1))

        return self._commit_record(
            operation="complete_todo", idempotency_key=idempotency_key,
            source_text=f"complete todo {todo_id}", requested_scope="todo", tool="todo.write",
            target_category="todo", target_table=None, target_values=None, result_key="todo_id",
            job_type="index_todo", pre_commit=pre_commit, side_effect=transition,
            existing_target_id=todo_id,
        )

    def get_expense_summary(self, *, currency: str | None = None) -> dict[str, Any]:
        expenses = self.tables["expenses"]
        predicates = [
            expenses.c.owner_id == self._db_id(expenses, "owner_id", self.owner_id),
            expenses.c.lifecycle_state == "active",
        ]
        if currency:
            predicates.append(expenses.c.currency == currency.upper())
        with self._session_factory() as session:
            self._assert_authority(session)
            rows = session.execute(sa.select(
                expenses.c.currency, sa.func.sum(expenses.c.amount).label("total"),
                sa.func.count().label("count"),
            ).where(*predicates).group_by(expenses.c.currency).order_by(expenses.c.currency)).mappings().all()
        return {"totals": [{
            "currency": row["currency"], "amount": f"{Decimal(row['total']):.4f}",
            "record_count": int(row["count"]),
        } for row in rows], "conversion_applied": False}

    def get_self_context(self, *, categories: list[str] | None = None) -> dict[str, Any]:
        claims = self.tables["self_claims"]
        # D2: the profile view shows what the brain currently holds (candidate
        # proposals plus active beliefs). Superseded duplicates, expired and
        # historical rows stay in the database for audit but are not re-stated
        # as if they were separate standing claims.
        predicates = [
            claims.c.owner_id == self._db_id(claims, "owner_id", self.owner_id),
            claims.c.lifecycle_state.in_(("candidate", "active")),
        ]
        if categories:
            predicates.append(claims.c.category.in_(categories))
        with self._session_factory() as session:
            self._assert_authority(session)
            rows = session.execute(sa.select(claims).where(*predicates).order_by(
                claims.c.created_at, claims.c.id,
            )).mappings().all()
        return {"claims": [{
            "claim_id": self._external_id(row["id"]), "category": row["category"],
            "claim": row["claim"], "policy_class": row["policy_class"],
            "lifecycle_state": row["lifecycle_state"], "review": row["review"],
            "evidence_summary": list(row["evidence_summary"] or []),
        } for row in rows]}

    def upload_asset(
        self, *, content: bytes, original_name: str, media_type: str, source_id: UUID,
        idempotency_key: UUID, storage: StorageBackend,
        pre_commit: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        required = {"asset_blobs", "assets"}
        if not required <= set(self.tables):
            raise RuntimeError(f"authoritative schema missing tables: {sorted(required - set(self.tables))}")
        sha256 = hashlib.sha256(content).hexdigest()
        stored = storage.store_atomic(
            io.BytesIO(content), expected_sha256=sha256, expected_size=len(content), content_type=media_type,
        )
        now = _utcnow()
        blobs, assets = self.tables["asset_blobs"], self.tables["assets"]
        raw, intake = self.tables["raw_inputs"], self.tables["intake_requests"]
        jobs, audit, idempotency = self.tables["jobs"], self.tables["audit_events"], self.tables["idempotency_records"]
        intake_id, asset_id, job_id, audit_id, correlation_id = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        with UnitOfWork(self._session_factory) as uow:
            session = uow.session
            self._assert_authority(session)
            source_key = self._db_id(raw, "id", source_id)
            source_exists = session.execute(sa.select(raw.c.id).where(
                raw.c.id == source_key,
                raw.c.owner_id == self._db_id(raw, "owner_id", self.owner_id),
                raw.c.lifecycle_state == "active",
            )).scalar_one_or_none()
            if source_exists is None:
                raise BrainError("NOT_FOUND")
            claim = claim_request(
                session, idempotency, owner_id=self.owner_id, client_id=self.client_id,
                operation="upload_asset", idempotency_key=idempotency_key,
                payload_digest=_digest({"sha256": sha256, "size": len(content), "name": original_name}),
            )
            if claim.state == "replay":
                return dict(claim.outcome or {})
            if claim.state != "created":
                raise BrainError("BRAIN_UNAVAILABLE")
            existing = session.execute(sa.select(blobs).where(
                blobs.c.owner_id == self._db_id(blobs, "owner_id", self.owner_id),
                blobs.c.sha256 == sha256, blobs.c.size_bytes == len(content),
            )).mappings().one_or_none()
            deduplicated = existing is not None
            if existing is None:
                blob_id = uuid4()
                session.execute(blobs.insert().values(
                    id=self._db_id(blobs, "id", blob_id),
                    owner_id=self._db_id(blobs, "owner_id", self.owner_id), sha256=sha256,
                    size_bytes=len(content), storage_backend=type(storage).__name__,
                    storage_key=stored.storage_key, reference_count=1, first_seen_at=now,
                    last_integrity_check_at=now,
                ))
            else:
                blob_id = existing["id"]
                session.execute(blobs.update().where(blobs.c.id == blob_id).values(
                    reference_count=int(existing["reference_count"]) + 1,
                    last_integrity_check_at=now,
                ))
            session.execute(intake.insert().values(
                id=self._db_id(intake, "id", intake_id), owner_id=self._db_id(intake, "owner_id", self.owner_id),
                client_id=self._db_id(intake, "client_id", self.client_id), operation="upload_asset",
                idempotency_key=self._db_id(intake, "idempotency_key", idempotency_key), received_at=now,
                content_ref=stored.storage_key, detected_intent="asset.upload", declared_intent="asset.upload",
                requested_scope="asset", security_decision="allow", intake_level="L1", state="completed",
                outcome_refs=[str(asset_id), str(blob_id)],
                correlation_id=self._db_id(intake, "correlation_id", correlation_id), error_code=None,
            ))
            session.execute(assets.insert().values(
                id=self._db_id(assets, "id", asset_id), owner_id=self._db_id(assets, "owner_id", self.owner_id),
                blob_id=self._db_id(assets, "blob_id", blob_id if isinstance(blob_id, UUID) else UUID(str(blob_id))),
                original_name=original_name, media_type=media_type, size_bytes=len(content), sha256=sha256,
                storage_backend=type(storage).__name__, storage_key=stored.storage_key,
                source_id=self._db_id(assets, "source_id", source_id), user_metadata={}, capture_at=None,
                location_evidence=None, integrity_state="valid", processing_state="queued", retention="canonical",
            ))
            session.execute(jobs.insert().values(
                id=self._db_id(jobs, "id", job_id), owner_id=self._db_id(jobs, "owner_id", self.owner_id),
                client_id=self._db_id(jobs, "client_id", self.client_id), job_type="parse_asset",
                payload_ref=f"asset:{asset_id}", idempotency_key=self._db_id(jobs, "idempotency_key", idempotency_key),
                state="queued", priority=0, attempts=0, max_attempts=5, available_at=now, claim_token=0,
            ))
            session.execute(audit.insert().values(
                id=self._db_id(audit, "id", audit_id), owner_id=self._db_id(audit, "owner_id", self.owner_id),
                client_id=self._db_id(audit, "client_id", self.client_id),
                correlation_id=self._db_id(audit, "correlation_id", correlation_id), action="upload_asset",
                tool="asset.write", effective_scope="asset", target_category="asset",
                target_id=self._db_id(audit, "target_id", asset_id), outcome="completed", error_code=None,
                duration_ms=0, occurred_at=now, risk="ordinary", authorization_decision="allow",
            ))
            outcome = {
                "status": "accepted", "persistence": "canonical_committed", "asset_id": str(asset_id),
                "blob_id": self._external_id(blob_id), "sha256": sha256, "storage_key": stored.storage_key,
                "deduplicated": deduplicated, "operation_id": str(intake_id),
            }
            complete_claim(session, idempotency, claim_id=claim.id, outcome=outcome)
            if pre_commit is not None:
                pre_commit()
            uow.commit()
        return outcome

    def start_project_task(
        self, *, project_id: UUID, goal: str, revision: str, dirty_state: bool,
        constraints: list[str], idempotency_key: UUID, plan: str | None = None,
        affected_modules: list[str] | None = None,
        pre_commit: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        projects = self.tables["projects"]
        with self._session_factory() as session:
            exists = session.execute(sa.select(projects.c.id).where(
                projects.c.id == self._db_id(projects, "id", project_id),
                projects.c.owner_id == self._db_id(projects, "owner_id", self.owner_id),
            )).scalar_one_or_none()
        if exists is None:
            raise BrainError("NOT_FOUND")
        return self._commit_record(
            operation="start_task", idempotency_key=idempotency_key, source_text=goal,
            requested_scope=f"project:{project_id}", tool="project.write",
            target_category="project_task", target_table="project_tasks", result_key="task_id",
            job_type="refresh_project_context",
            target_values=lambda _target, _source, now: {
                "project_id": self._db_id(self.tables["project_tasks"], "project_id", project_id),
                "goal": goal, "state": "active", "start_revision": revision, "end_revision": None,
                "start_dirty_state": dirty_state, "end_dirty_state": None, "plan": plan,
                "constraints": constraints, "affected_modules": affected_modules or [], "started_at": now,
                "completed_at": None, "remaining_work": None, "final_report": None,
            },
            pre_commit=pre_commit,
        )

    def checkpoint_project_task(
        self, *, task_id: UUID, completed_work: str, next_step: str,
        problems: str, revision: str | None, idempotency_key: UUID,
        dirty_files: list[str] | None = None, changed_files: list[str] | None = None,
        decisions: list[str] | None = None, verification_evidence: str | None = None,
        pre_commit: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        tasks = self.tables["project_tasks"]
        with self._session_factory() as session:
            exists = session.execute(sa.select(tasks.c.id).where(
                tasks.c.id == self._db_id(tasks, "id", task_id),
                tasks.c.owner_id == self._db_id(tasks, "owner_id", self.owner_id),
            )).scalar_one_or_none()
        if exists is None:
            raise BrainError("NOT_FOUND")
        return self._commit_record(
            operation="checkpoint_task", idempotency_key=idempotency_key,
            source_text=completed_work, requested_scope="project", tool="project.write",
            target_category="checkpoint", target_table="checkpoints", result_key="checkpoint_id",
            job_type="refresh_project_context",
            target_values=lambda _target, _source, now: {
                "task_id": self._db_id(self.tables["checkpoints"], "task_id", task_id),
                "revision": revision, "dirty_files": dirty_files or [], "changed_files": changed_files or [],
                "completed_work": completed_work, "problems": problems, "decisions": decisions or [],
                "next_step": next_step, "verification_evidence": verification_evidence, "captured_at": now,
            },
            pre_commit=pre_commit,
        )

    def record_project_fact(
        self, *, kind: str, project_id: UUID, statement: str, rationale: str,
        affected_modules: list[str], idempotency_key: UUID,
        pre_commit: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        if kind not in {"decision", "constraint"}:
            raise ValueError("kind must be decision or constraint")
        table_name = f"{kind}s"
        dedupe = f"{kind}:{statement.strip().lower()}"
        # The (owner_id, deduplication_key) unique constraint is an intentional
        # content dedupe. A repeat statement must replay the existing record
        # idempotently instead of surfacing a UniqueViolation as HTTP 500.
        table = self.tables[table_name]
        with self._session_factory() as session:
            existing = session.execute(sa.select(
                table.c.id, table.c.project_id, table.c.lifecycle_state,
            ).where(
                table.c.owner_id == self._db_id(table, "owner_id", self.owner_id),
                table.c.deduplication_key == dedupe,
            )).first()
        if existing is not None:
            if existing.lifecycle_state != "active":
                # The same statement was recorded before and has since been
                # deleted (its project was removed): deleted content is never
                # recreated, and the unique key would reject a fresh insert
                # anyway — answer with the tombstone instead of a 500.
                return {
                    "status": "deleted", "persistence": "tombstone", "deduplicated": True,
                    f"{kind}_id": str(existing.id),
                    "existing_project_id": str(existing.project_id),
                    "operation_id": str(idempotency_key),
                }
            return {
                "status": "duplicate", "persistence": "canonical_committed",
                "deduplicated": True, f"{kind}_id": str(existing.id),
                "existing_project_id": str(existing.project_id),
                "operation_id": str(idempotency_key),
            }
        return self._commit_record(
            operation=f"record_{kind}", idempotency_key=idempotency_key,
            source_text=statement, requested_scope=f"project:{project_id}",
            tool="project.write", target_category=kind, target_table=table_name,
            result_key=f"{kind}_id", job_type="refresh_project_context",
            target_values=lambda _target, source, now: {
                "project_id": self._db_id(self.tables[table_name], "project_id", project_id),
                "module_id": None, "task_id": None, "statement": statement,
                "rationale": rationale, "evidence": [],
                "source_id": self._db_id(self.tables[table_name], "source_id", source),
                "valid_from": now, "valid_to": None, "lifecycle_state": "active",
                "deduplication_key": dedupe, "affected_modules": affected_modules,
                "revisions": [],
            }, pre_commit=pre_commit,
        )

    def finalize_project_task(
        self, *, task_id: UUID, outcome: str, verification: str, remaining_work: str,
        end_revision: str | None, end_dirty_state: bool | None,
        changed_files: list[str], idempotency_key: UUID,
        pre_commit: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        tasks = self.tables["project_tasks"]
        with self._session_factory() as session:
            task = session.execute(sa.select(tasks).where(
                tasks.c.id == self._db_id(tasks, "id", task_id),
                tasks.c.owner_id == self._db_id(tasks, "owner_id", self.owner_id),
            )).mappings().one_or_none()
        if task is None:
            raise BrainError("NOT_FOUND")
        project_id = UUID(str(task["project_id"]))
        report = json.dumps({
            "goal": task["goal"], "outcome": outcome, "start_revision": task["start_revision"],
            "end_revision": end_revision, "changed_files": changed_files,
            "verification": verification, "remaining_work": remaining_work,
        }, ensure_ascii=False, sort_keys=True)

        def finish(session: Session, _target: UUID, _source: UUID, now: datetime) -> None:
            session.execute(tasks.update().where(
                tasks.c.id == self._db_id(tasks, "id", task_id),
                tasks.c.owner_id == self._db_id(tasks, "owner_id", self.owner_id),
                tasks.c.state.in_(("planned", "active", "paused")),
            ).values(
                state="completed", end_revision=end_revision, end_dirty_state=end_dirty_state,
                completed_at=now, remaining_work=remaining_work, final_report=report,
            ))

        return self._commit_record(
            operation="finalize_task", idempotency_key=idempotency_key, source_text=report,
            requested_scope=f"project:{project_id}", tool="project.write",
            target_category="change_event", target_table="change_events",
            result_key="change_event_id", job_type="refresh_project_context",
            target_values=lambda _target, source, now: {
                "project_id": self._db_id(self.tables["change_events"], "project_id", project_id),
                "module_id": None,
                "task_id": self._db_id(self.tables["change_events"], "task_id", task_id),
                "statement": outcome, "rationale": verification,
                "evidence": {"changed_files": changed_files},
                "source_id": self._db_id(self.tables["change_events"], "source_id", source),
                "valid_from": now, "valid_to": None, "lifecycle_state": "active",
                "deduplication_key": f"finalize:{task_id}:{idempotency_key}",
                "affected_modules": list(task["affected_modules"] or []),
                "revisions": [item for item in (task["start_revision"], end_revision) if item],
            }, pre_commit=pre_commit, side_effect=finish,
        )

    def sync_workspace(
        self, *, project_id: UUID, approved_root_identity: str, revision: str | None,
        branch_ref: str | None, dirty_state: bool | None, changed_paths: list[str],
        file_hashes: dict[str, str], modules: list[dict[str, Any]], bridge_client_id: str,
        idempotency_key: UUID,
    ) -> dict[str, Any]:
        """Persist a bounded observation and atomically refresh/invalidate module cards."""
        if not approved_root_identity or len(changed_paths) > 1000 or len(file_hashes) > 5000:
            raise BrainError("VALIDATION_FAILED")
        required = {"projects", "module_cards", "workspace_observations"}
        if not required <= set(self.tables):
            raise RuntimeError(f"authoritative schema missing tables: {sorted(required - set(self.tables))}")
        projects, cards, observations = (self.tables[name] for name in (
            "projects", "module_cards", "workspace_observations",
        ))
        now, observation_id = _utcnow(), uuid4()
        intake_id, source_id, job_id, audit_id, correlation_id = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
        owner = self._db_id(projects, "owner_id", self.owner_id)
        project_key = self._db_id(projects, "id", project_id)
        with UnitOfWork(self._session_factory) as uow:
            session = uow.session
            self._assert_authority(session)
            project = session.execute(sa.select(projects).where(
                projects.c.id == project_key, projects.c.owner_id == owner,
            )).mappings().one_or_none()
            if project is None:
                raise BrainError("NOT_FOUND")
            if project["workspace_identity"] not in (None, approved_root_identity):
                raise BrainError("WORKSPACE_BOUNDARY_VIOLATION")
            payload = {
                "project_id": str(project_id), "root": approved_root_identity,
                "revision": revision, "branch": branch_ref, "dirty": dirty_state,
                "changed_paths": changed_paths, "file_hashes": file_hashes, "modules": modules,
            }
            claim = claim_request(
                session, self.tables["idempotency_records"], owner_id=self.owner_id,
                client_id=self.client_id, operation="sync_workspace",
                idempotency_key=idempotency_key, payload_digest=_digest(payload),
            )
            if claim.state == "replay":
                return dict(claim.outcome or {})
            if claim.state != "created":
                raise BrainError("BRAIN_UNAVAILABLE")
            source_text = json.dumps({
                "revision": revision, "changed_paths": changed_paths,
            }, ensure_ascii=False, sort_keys=True)
            session.execute(self.tables["intake_requests"].insert().values(
                id=self._db_id(self.tables["intake_requests"], "id", intake_id),
                owner_id=self._db_id(self.tables["intake_requests"], "owner_id", self.owner_id),
                client_id=self._db_id(self.tables["intake_requests"], "client_id", self.client_id),
                operation="sync_workspace",
                idempotency_key=self._db_id(self.tables["intake_requests"], "idempotency_key", idempotency_key),
                received_at=now, content_ref=None, detected_intent="project.sync",
                declared_intent="project.sync", requested_scope=f"project:{project_id}",
                security_decision="allow", intake_level="L1", state="processing", outcome_refs=[],
                correlation_id=self._db_id(self.tables["intake_requests"], "correlation_id", correlation_id),
                error_code=None,
            ))
            session.execute(self.tables["raw_inputs"].insert().values(
                id=self._db_id(self.tables["raw_inputs"], "id", source_id),
                owner_id=self._db_id(self.tables["raw_inputs"], "owner_id", self.owner_id),
                intake_request_id=self._db_id(self.tables["raw_inputs"], "intake_request_id", intake_id),
                client_id=self._db_id(self.tables["raw_inputs"], "client_id", self.client_id),
                content_text=source_text, asset_ref=None,
                content_hash=hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
                original_at=now, original_timezone="UTC", source_channel="bridge",
                language=None, retention_policy="canonical", sensitivity="private",
                information_class="observation", canonicality="canonical",
                source_kind="observation",
                source_id=self._db_id(self.tables["raw_inputs"], "source_id", source_id),
                valid_from=now, valid_to=None, lifecycle_state="active", deleted_at=None,
            ))
            session.execute(observations.insert().values(
                id=self._db_id(observations, "id", observation_id),
                owner_id=self._db_id(observations, "owner_id", self.owner_id),
                project_id=self._db_id(observations, "project_id", project_id),
                approved_root_identity=approved_root_identity, revision=revision,
                branch_ref=branch_ref, dirty_state=dirty_state,
                changed_paths=changed_paths, diff_summary=None, file_hashes=file_hashes,
                observed_at=now, bridge_client_id=bridge_client_id,
            ))
            supplied_names: set[str] = set()
            for module in modules[:1000]:
                name = str(module["name"])
                supplied_names.add(name)
                paths = list(module.get("paths") or [])
                hashes = dict(module.get("file_hashes") or {})
                current = session.execute(sa.select(cards).where(
                    cards.c.owner_id == self._db_id(cards, "owner_id", self.owner_id),
                    cards.c.project_id == self._db_id(cards, "project_id", project_id),
                    cards.c.name == name,
                )).mappings().one_or_none()
                values = {
                    "paths": paths, "core_files": list(module.get("core_files") or [])[:50],
                    "dependencies": list(module.get("dependencies") or []),
                    "indexed_revision": revision, "relevant_file_hashes": hashes,
                    "freshness": "fresh" if revision else "unknown", "stale_reasons": [],
                    "refreshed_at": now, "updated_at": now,
                }
                if current is None:
                    session.execute(cards.insert().values(
                        id=self._db_id(cards, "id", uuid4()),
                        owner_id=self._db_id(cards, "owner_id", self.owner_id),
                        project_id=self._db_id(cards, "project_id", project_id),
                        name=name, responsibility=module.get("responsibility"), interfaces=[],
                        consumers=[], constraints=[], **values,
                    ))
                else:
                    session.execute(cards.update().where(cards.c.id == current["id"]).values(**values))
            existing = session.execute(sa.select(cards).where(
                cards.c.owner_id == self._db_id(cards, "owner_id", self.owner_id),
                cards.c.project_id == self._db_id(cards, "project_id", project_id),
            )).mappings().all()
            for card in existing:
                if card["name"] in supplied_names:
                    continue
                prefixes = list(card["paths"] or [])
                touched = any(
                    changed == prefix.rstrip("/") or changed.startswith(prefix.rstrip("/") + "/")
                    for changed in changed_paths for prefix in prefixes
                )
                if touched:
                    session.execute(cards.update().where(cards.c.id == card["id"]).values(
                        freshness="stale", stale_reasons=["workspace evidence changed since indexing"],
                        updated_at=now,
                    ))
            session.execute(projects.update().where(projects.c.id == project_key).values(
                workspace_identity=approved_root_identity,
                current_revision_evidence={
                    "revision": revision, "branch": branch_ref, "dirty": dirty_state,
                    "observation_id": str(observation_id), "observed_at": now.isoformat(),
                }, directory_overview=json.dumps([item["name"] for item in modules], ensure_ascii=False),
                updated_at=now,
            ))
            session.execute(self.tables["jobs"].insert().values(
                id=self._db_id(self.tables["jobs"], "id", job_id),
                owner_id=self._db_id(self.tables["jobs"], "owner_id", self.owner_id),
                client_id=self._db_id(self.tables["jobs"], "client_id", self.client_id),
                job_type="refresh_project_context", payload_ref=f"workspace_observation:{observation_id}",
                idempotency_key=self._db_id(self.tables["jobs"], "idempotency_key", idempotency_key),
                state="queued", priority=0, attempts=0, max_attempts=5, available_at=now, claim_token=0,
            ))
            session.execute(self.tables["audit_events"].insert().values(
                id=self._db_id(self.tables["audit_events"], "id", audit_id),
                owner_id=self._db_id(self.tables["audit_events"], "owner_id", self.owner_id),
                client_id=self._db_id(self.tables["audit_events"], "client_id", self.client_id),
                correlation_id=self._db_id(self.tables["audit_events"], "correlation_id", correlation_id),
                action="sync_workspace", tool="project.write", effective_scope=f"project:{project_id}",
                target_category="workspace_observation",
                target_id=self._db_id(self.tables["audit_events"], "target_id", observation_id),
                outcome="completed", error_code=None, duration_ms=0, occurred_at=now,
                risk="ordinary", authorization_decision="allow",
            ))
            outcome = {
                "status": "accepted", "persistence": "canonical_committed",
                "observation_id": str(observation_id), "refreshed_modules": sorted(supplied_names),
                "operation_id": str(intake_id),
            }
            session.execute(self.tables["intake_requests"].update().where(
                self.tables["intake_requests"].c.id == self._db_id(
                    self.tables["intake_requests"], "id", intake_id,
                ),
            ).values(state="completed", outcome_refs=[str(observation_id)]))
            complete_claim(session, self.tables["idempotency_records"], claim_id=claim.id, outcome=outcome)
            if uow.session.in_transaction():
                uow.commit()
        return outcome

    def list_projects(self) -> dict[str, Any]:
        """Enumerate the owner's live projects (discovery for the projects channel).

        Tombstoned projects stay in canonical storage but are not listed: a
        client that deleted a project must not keep seeing it in discovery.
        """
        projects = self.tables["projects"]
        with self._session_factory() as session:
            self._assert_authority(session)
            rows = session.execute(sa.select(projects).where(
                projects.c.owner_id == self._db_id(projects, "owner_id", self.owner_id),
                projects.c.lifecycle_state == "active",
            ).order_by(projects.c.created_at, projects.c.id)).mappings().all()
        return {"projects": [{
            "project_id": self._external_id(row["id"]), "name": row["name"],
            "purpose": row["purpose"], "lifecycle_state": row["lifecycle_state"],
            "version": row["version"],
        } for row in rows]}

    def get_project_recovery(self, project_id: UUID) -> dict[str, Any]:
        projects, tasks, checkpoints = (
            self.tables["projects"], self.tables["project_tasks"], self.tables["checkpoints"],
        )
        owner = self._db_id(projects, "owner_id", self.owner_id)
        project_key = self._db_id(projects, "id", project_id)
        with self._session_factory() as session:
            self._assert_authority(session)
            project = session.execute(sa.select(projects).where(
                projects.c.id == project_key, projects.c.owner_id == owner,
                projects.c.lifecycle_state == "active",
            )).mappings().one_or_none()
            if project is None:
                # A tombstoned project is gone for readers too: its recovery view
                # must not be reconstructable after governed deletion.
                raise BrainError("NOT_FOUND")
            active = session.execute(sa.select(tasks).where(
                tasks.c.owner_id == self._db_id(tasks, "owner_id", self.owner_id),
                tasks.c.project_id == self._db_id(tasks, "project_id", project_id),
                tasks.c.state == "active",
            ).order_by(tasks.c.started_at.desc()).limit(1)).mappings().one_or_none()
            checkpoint_rows = [] if active is None else session.execute(sa.select(checkpoints).where(
                checkpoints.c.owner_id == self._db_id(checkpoints, "owner_id", self.owner_id),
                checkpoints.c.task_id == active["id"],
            ).order_by(checkpoints.c.captured_at)).mappings().all()
            card_rows = [] if "module_cards" not in self.tables else session.execute(sa.select(self.tables["module_cards"]).where(
                self.tables["module_cards"].c.owner_id == self._db_id(
                    self.tables["module_cards"], "owner_id", self.owner_id,
                ),
                self.tables["module_cards"].c.project_id == self._db_id(
                    self.tables["module_cards"], "project_id", project_id,
                ),
            ).order_by(self.tables["module_cards"].c.name)).mappings().all()
            observation = None if "workspace_observations" not in self.tables else session.execute(sa.select(self.tables["workspace_observations"]).where(
                self.tables["workspace_observations"].c.owner_id == self._db_id(
                    self.tables["workspace_observations"], "owner_id", self.owner_id,
                ),
                self.tables["workspace_observations"].c.project_id == self._db_id(
                    self.tables["workspace_observations"], "project_id", project_id,
                ),
            ).order_by(self.tables["workspace_observations"].c.observed_at.desc()).limit(1)).mappings().one_or_none()
            facts: dict[str, list[dict[str, Any]]] = {}
            for fact_name in ("decisions", "constraints", "change_events"):
                if fact_name not in self.tables:
                    facts[fact_name] = []
                    continue
                fact_table = self.tables[fact_name]
                rows = session.execute(sa.select(fact_table).where(
                    fact_table.c.owner_id == self._db_id(fact_table, "owner_id", self.owner_id),
                    fact_table.c.project_id == self._db_id(fact_table, "project_id", project_id),
                    fact_table.c.lifecycle_state == "active",
                ).order_by(fact_table.c.created_at.desc()).limit(25)).mappings().all()
                facts[fact_name] = [{
                    "id": self._external_id(row["id"]), "statement": row["statement"],
                    "rationale": row["rationale"], "affected_modules": list(row["affected_modules"] or []),
                } for row in rows]
        return {
            "project_purpose": project["purpose"],
            "project": {
                "project_id": self._external_id(project["id"]), "name": project["name"],
                "purpose": project["purpose"], "goals": list(project["goals"] or []),
                "principles": list(project["principles"] or []),
                "workspace_identity": project["workspace_identity"],
            },
            "active_task": None if active is None else {
                "task_id": self._external_id(active["id"]), "goal": active["goal"], "state": active["state"],
                "start_revision": active["start_revision"], "start_dirty_state": active["start_dirty_state"],
                "constraints": list(active["constraints"] or []),
            },
            "checkpoints": [{
                "checkpoint_id": self._external_id(row["id"]),
                "completed_work": row["completed_work"], "next_step": row["next_step"],
                "revision": row["revision"], "problems": row["problems"],
            } for row in checkpoint_rows],
            "modules": [{
                "module_id": self._external_id(row["id"]), "name": row["name"],
                "paths": list(row["paths"] or []), "freshness": row["freshness"],
                "stale_reasons": list(row["stale_reasons"] or []),
                "indexed_revision": row["indexed_revision"],
            } for row in card_rows],
            "workspace_evidence": None if observation is None else {
                "revision": observation["revision"], "branch": observation["branch_ref"],
                "dirty": observation["dirty_state"],
                "changed_paths": list(observation["changed_paths"] or []),
                "observed_at": observation["observed_at"].isoformat(),
            },
            **facts,
            "next_step": checkpoint_rows[-1]["next_step"] if checkpoint_rows else "inspect current source before further modification",
        }

    @staticmethod
    def _db_id(table: sa.Table, column: str, value: UUID | None) -> UUID | str | None:
        if value is None:
            return None
        kind = table.c[column].type
        if isinstance(kind, sa.Uuid) and kind.as_uuid:
            return value
        if isinstance(kind, sa.String) and kind.length == 32:
            return value.hex
        return str(value)

    @staticmethod
    def _external_id(value: Any) -> str:
        return str(value if isinstance(value, UUID) else UUID(str(value)))

    def _assert_authority(self, session: Session) -> None:
        clients = self.tables["clients"]
        active = session.execute(
            sa.select(clients.c.id).where(
                clients.c.id == self._db_id(clients, "id", self.client_id),
                clients.c.owner_id == self._db_id(clients, "owner_id", self.owner_id),
                clients.c.status == "active",
            )
        ).scalar_one_or_none()
        if active is None:
            raise BrainError("PERMISSION_DENIED")

    def add_expense(
        self,
        *,
        amount: str,
        currency: str,
        category: str,
        description: str,
        occurred_timezone: str,
        requested_scope: str,
        idempotency_key: UUID,
        source_text: str,
        pre_commit: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "amount": amount,
            "currency": currency,
            "category": category,
            "description": description,
            "occurred_timezone": occurred_timezone,
            "requested_scope": requested_scope,
            "source_text": source_text,
        }
        digest = _digest(payload)
        now = _utcnow()
        intake_id, source_id, expense_id = uuid4(), uuid4(), uuid4()
        job_id, audit_id, correlation_id = uuid4(), uuid4(), uuid4()

        with UnitOfWork(self._session_factory) as uow:
            session = uow.session
            self._assert_authority(session)
            claim = claim_request(
                session,
                self.tables["idempotency_records"],
                owner_id=self.owner_id,
                client_id=self.client_id,
                operation="add_expense",
                idempotency_key=idempotency_key,
                payload_digest=digest,
            )
            if claim.state == "replay":
                return dict(claim.outcome or {})
            if claim.state == "deleted":
                return {"status": "deleted", "persistence": "tombstone"}
            if claim.state == "in_progress":
                raise BrainError("BRAIN_UNAVAILABLE")

            session.execute(self.tables["intake_requests"].insert().values(
                id=self._db_id(self.tables["intake_requests"], "id", intake_id),
                owner_id=self._db_id(self.tables["intake_requests"], "owner_id", self.owner_id),
                client_id=self._db_id(self.tables["intake_requests"], "client_id", self.client_id),
                operation="add_expense",
                idempotency_key=self._db_id(self.tables["intake_requests"], "idempotency_key", idempotency_key),
                received_at=now,
                content_ref=None,
                detected_intent="finance.expense.create",
                declared_intent="finance.expense.create",
                requested_scope=requested_scope,
                security_decision="allow",
                intake_level="L1",
                state="processing",
                outcome_refs=[],
                correlation_id=self._db_id(self.tables["intake_requests"], "correlation_id", correlation_id),
                error_code=None,
            ))
            session.execute(self.tables["raw_inputs"].insert().values(
                id=self._db_id(self.tables["raw_inputs"], "id", source_id),
                owner_id=self._db_id(self.tables["raw_inputs"], "owner_id", self.owner_id),
                intake_request_id=self._db_id(self.tables["raw_inputs"], "intake_request_id", intake_id),
                client_id=self._db_id(self.tables["raw_inputs"], "client_id", self.client_id),
                content_text=source_text,
                asset_ref=None,
                content_hash=hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
                original_at=now,
                original_timezone=occurred_timezone,
                source_channel="api",
                language="zh-CN",
                retention_policy="canonical",
                sensitivity="normal",
                information_class="explicit_user_statement",
                canonicality="canonical",
                source_kind="explicit_user_statement",
                source_id=self._db_id(self.tables["raw_inputs"], "source_id", source_id),
                valid_from=now,
                valid_to=None,
                lifecycle_state="active",
                deleted_at=None,
            ))
            session.execute(self.tables["expenses"].insert().values(
                id=self._db_id(self.tables["expenses"], "id", expense_id),
                owner_id=self._db_id(self.tables["expenses"], "owner_id", self.owner_id),
                amount=Decimal(amount),
                currency=currency.upper(),
                category=category,
                description=description,
                occurred_at=now,
                occurred_timezone=occurred_timezone,
                kind="expense",
                event_id=None,
                source_id=self._db_id(self.tables["expenses"], "source_id", source_id),
                sensitivity="normal",
                information_class="explicit_user_statement",
                canonicality="canonical",
                source_kind="explicit_user_statement",
                valid_from=now,
                valid_to=None,
                lifecycle_state="active",
                deleted_at=None,
            ))
            session.execute(self.tables["jobs"].insert().values(
                id=self._db_id(self.tables["jobs"], "id", job_id),
                owner_id=self._db_id(self.tables["jobs"], "owner_id", self.owner_id),
                client_id=self._db_id(self.tables["jobs"], "client_id", self.client_id),
                job_type="index_raw_input",
                payload_ref=f"raw_input:{source_id}",
                idempotency_key=self._db_id(self.tables["jobs"], "idempotency_key", idempotency_key),
                state="queued",
                priority=0,
                attempts=0,
                max_attempts=5,
                available_at=now,
                claim_token=0,
            ))
            session.execute(self.tables["audit_events"].insert().values(
                id=self._db_id(self.tables["audit_events"], "id", audit_id),
                owner_id=self._db_id(self.tables["audit_events"], "owner_id", self.owner_id),
                client_id=self._db_id(self.tables["audit_events"], "client_id", self.client_id),
                correlation_id=self._db_id(self.tables["audit_events"], "correlation_id", correlation_id),
                action="add_expense",
                tool="finance.write",
                effective_scope=requested_scope,
                target_category="expense",
                target_id=self._db_id(self.tables["audit_events"], "target_id", expense_id),
                outcome="completed",
                error_code=None,
                duration_ms=0,
                occurred_at=now,
                risk="ordinary",
                authorization_decision="allow",
            ))
            outcome = {
                "status": "accepted",
                "persistence": "canonical_committed",
                "expense_id": str(expense_id),
                "source_id": str(source_id),
            }
            session.execute(
                self.tables["intake_requests"].update()
                .where(self.tables["intake_requests"].c.id == self._db_id(self.tables["intake_requests"], "id", intake_id))
                .values(state="completed", outcome_refs=[outcome["expense_id"], outcome["source_id"]])
            )
            complete_claim(
                session,
                self.tables["idempotency_records"],
                claim_id=claim.id,
                outcome=outcome,
            )
            if pre_commit is not None:
                pre_commit()
            uow.commit()
        return outcome

    def list_expenses(self) -> list[dict[str, str]]:
        expenses = self.tables["expenses"]
        with self._session_factory() as session:
            self._assert_authority(session)
            rows = session.execute(
                sa.select(expenses).where(
                    expenses.c.owner_id == self._db_id(expenses, "owner_id", self.owner_id),
                    expenses.c.lifecycle_state == "active",
                ).order_by(expenses.c.occurred_at, expenses.c.id)
            ).mappings()
            return [
                {
                    "expense_id": self._external_id(row["id"]),
                    "amount": f"{Decimal(row['amount']):.4f}",
                    "currency": row["currency"],
                    "category": row["category"],
                    "description": row["description"],
                    "source_id": self._external_id(row["source_id"]),
                }
                for row in rows
            ]
