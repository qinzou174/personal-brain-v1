"""Durable-job search indexing from authoritative canonical rows."""

from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

import sqlalchemy as sa

from personal_brain_domain.common.errors import BrainError
from personal_brain_infra.search.repository import PostgresSearchRepository


class SearchIndexer:
    def __init__(self, session_factory: Any, tables: Mapping[str, sa.Table], embedder: Any | None = None) -> None:
        self._factory = session_factory
        self._tables = tables
        self._embedder = embedder

    def handle(self, job: dict[str, Any]) -> dict[str, Any]:
        try:
            target_type, raw_id = job["payload_ref"].split(":", 1)
            target_id = UUID(raw_id)
            owner_id = UUID(str(job["owner_id"]))
        except (ValueError, AttributeError) as error:
            raise BrainError("VALIDATION_FAILED") from error
        if target_type == "raw_input":
            entry = self._raw_input(owner_id, target_id)
        elif target_type == "todo":
            entry = self._simple(owner_id, target_id, "todos", "content", "todo")
        elif target_type == "self_claim":
            entry = self._simple(owner_id, target_id, "self_claims", "claim", "self")
        elif target_type in {"decision", "constraint", "change_event"}:
            entry = self._fact(owner_id, target_type, target_id)
        elif target_type in {"project", "project_task", "checkpoint", "workspace_observation"}:
            entry = self._project(owner_id, target_type, target_id)
        else:
            raise BrainError("VALIDATION_FAILED")
        repository = PostgresSearchRepository(
            self._factory, self._tables["search_index_entries"], owner_id=owner_id,
        )
        warnings: list[str] = []
        if self._embedder is not None:
            try:
                entry["embedding"] = self._embedder.embed(entry["text"])
            except BrainError as error:
                # Decision (b), 2026-09-25: secret-like content keeps its canonical
                # raw text locally (*never* sent to an embedding provider), so the
                # card degrades to keyword-only instead of dead-lettering the job.
                # The skip is declared on the card so retrieval stays honest.
                if error.code != "SECRET_REJECTED":
                    raise
                warnings.append("secret_like_semantic_skipped")
            else:
                entry["vector_model_version"] = self._embedder.model_version
        entry_id = repository.index(**entry, warnings=warnings)
        result: dict[str, Any] = {
            "search_entry_id": entry_id, "target_ref": f"{target_type}:{target_id}",
            "indexed": True,
        }
        if warnings:
            result["warnings"] = warnings
        return result

    def _raw_input(self, owner_id: UUID, target_id: UUID) -> dict[str, Any]:
        raw, intake = self._tables["raw_inputs"], self._tables["intake_requests"]
        with self._factory() as session:
            row = session.execute(sa.select(raw, intake.c.requested_scope).join(
                intake, intake.c.id == raw.c.intake_request_id,
            ).where(raw.c.id == target_id, raw.c.owner_id == owner_id,
                    raw.c.lifecycle_state == "active")).mappings().one_or_none()
        if row is None or not row["content_text"]:
            raise BrainError("NOT_FOUND")
        return self._entry(
            "raw_input", target_id, row["requested_scope"], row["sensitivity"],
            row["canonicality"], "fresh", row["content_text"], [f"raw_input:{target_id}"],
        )

    def _simple(self, owner_id: UUID, target_id: UUID, table_name: str,
                text_column: str, scope: str) -> dict[str, Any]:
        table = self._tables[table_name]
        with self._factory() as session:
            row = session.execute(sa.select(table).where(
                table.c.id == target_id, table.c.owner_id == owner_id,
                table.c.lifecycle_state.in_(("active", "candidate")),
            )).mappings().one_or_none()
        if row is None:
            raise BrainError("NOT_FOUND")
        return self._entry(
            table_name.rstrip("s"), target_id, scope, row.get("sensitivity", "private"),
            row.get("canonicality", "canonical"), "fresh", row[text_column],
            [f"{table_name.rstrip('s')}:{target_id}"] + ([f"raw_input:{row['source_id']}"] if row.get("source_id") else []),
        )

    def _fact(self, owner_id: UUID, target_type: str, target_id: UUID) -> dict[str, Any]:
        """Index a project fact (decision/constraint/change_event) into its
        project scope — record_project_fact enqueues a refresh job with this
        payload_ref, and the indexer used to reject it as unknown."""
        table = self._tables[{"decision": "decisions", "constraint": "constraints",
                              "change_event": "change_events"}[target_type]]
        with self._factory() as session:
            row = session.execute(sa.select(table).where(
                table.c.id == target_id, table.c.owner_id == owner_id,
                table.c.lifecycle_state == "active",
            )).mappings().one_or_none()
        if row is None:
            raise BrainError("NOT_FOUND")
        text = f"{row['statement']} {row['rationale'] or ''}".strip()
        if not text:
            text = target_type  # the embedder rejects blank input
        return self._entry(
            target_type, target_id, f"project:{row['project_id']}", "private",
            "canonical", "fresh", text,
            [f"{target_type}:{target_id}", f"project:{row['project_id']}"],
        )

    def _project(self, owner_id: UUID, target_type: str, target_id: UUID) -> dict[str, Any]:
        table_name = {
            "project": "projects", "project_task": "project_tasks",
            "checkpoint": "checkpoints", "workspace_observation": "workspace_observations",
        }[target_type]
        table = self._tables[table_name]
        with self._factory() as session:
            row = session.execute(sa.select(table).where(
                table.c.id == target_id, table.c.owner_id == owner_id,
            )).mappings().one_or_none()
            if row is None:
                raise BrainError("NOT_FOUND")
            if target_type == "project":
                project_id, text = target_id, f"{row['name']} {row['purpose']}"
            elif target_type == "project_task":
                project_id, text = row["project_id"], f"{row['goal']} {row['plan'] or ''} {row['final_report'] or ''}"
            elif target_type == "checkpoint":
                task = session.execute(sa.select(self._tables["project_tasks"]).where(
                    self._tables["project_tasks"].c.id == row["task_id"],
                    self._tables["project_tasks"].c.owner_id == owner_id,
                )).mappings().one()
                project_id, text = task["project_id"], f"{row['completed_work']} {row['problems'] or ''} {row['next_step'] or ''}"
            else:
                project_id, text = row["project_id"], " ".join(row["changed_paths"] or [])
        return self._entry(
            target_type, target_id, f"project:{project_id}", "private", "canonical",
            "fresh", text, [f"{target_type}:{target_id}"],
        )

    @staticmethod
    def _entry(target_type: str, target_id: UUID, scope: str, sensitivity: str,
               canonicality: str, freshness: str, text: str,
               sources: list[str]) -> dict[str, Any]:
        return {
            "target_type": target_type, "target_id": target_id, "authorized_scope": scope,
            "sensitivity": sensitivity, "canonicality": canonicality,
            "freshness": freshness, "text": text, "source_links": sources,
        }
