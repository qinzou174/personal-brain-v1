"""Durable-job search indexing from authoritative canonical rows."""

from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

import sqlalchemy as sa

from personal_brain_domain.common.errors import BrainError
from personal_brain_infra.search.repository import PostgresSearchRepository


class SearchIndexer:
    def __init__(self, session_factory: Any, tables: Mapping[str, sa.Table], embedder: Any | None = None,
                 storage: Any | None = None) -> None:
        self._factory = session_factory
        self._tables = tables
        self._embedder = embedder
        # Derived payloads (extracted text, transcripts, descriptions) live in
        # storage rather than in a column, so indexing them needs the backend.
        self._storage = storage

    def handle(self, job: dict[str, Any]) -> dict[str, Any]:
        try:
            target_type, raw_id = job["payload_ref"].split(":", 1)
            target_id = UUID(raw_id)
            owner_id = UUID(str(job["owner_id"]))
        except (ValueError, AttributeError) as error:
            raise BrainError("VALIDATION_FAILED") from error
        try:
            entry = self._entry_for(owner_id, target_type, target_id)
        except BrainError as error:
            if error.code != "NOT_FOUND":
                raise
            # A refresh can legitimately race a governed deletion: by execution
            # time the source is tombstoned (or superseded). The projection of an
            # absent source is *no card*, so settle the job as a declared skip —
            # dead-lettering it would turn every deletion into a health alert.
            # Deletion already removed surviving cards via reconcile_deletion.
            return {"target_ref": f"{target_type}:{target_id}", "indexed": False,
                    "skipped": "source_gone"}
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

    def _entry_for(self, owner_id: UUID, target_type: str, target_id: UUID) -> dict[str, Any]:
        """Resolve the canonical row into a retrieval card (NOT_FOUND when gone)."""
        if target_type == "raw_input":
            return self._raw_input(owner_id, target_id)
        if target_type == "todo":
            return self._simple(owner_id, target_id, "todos", "content", "todo")
        if target_type == "self_claim":
            return self._simple(owner_id, target_id, "self_claims", "claim", "self")
        if target_type in {"decision", "constraint", "change_event"}:
            return self._fact(owner_id, target_type, target_id)
        if target_type == "derived_content":
            return self._derived_content(owner_id, target_id)
        if target_type in {"project", "project_task", "checkpoint", "workspace_observation"}:
            return self._project(owner_id, target_type, target_id)
        raise BrainError("VALIDATION_FAILED")

    def _derived_content(self, owner_id: UUID, target_id: UUID) -> dict[str, Any]:
        """Index an asset-derived payload (its text lives in storage).

        Only asset derivations are handled here: digests are scope-grouped and
        already index themselves, so re-projecting one from this path could
        attribute its text to the wrong scope. Without a storage backend the
        payload cannot be read at all, which is reported instead of guessing.
        """
        table = self._tables["derived_contents"]
        with self._factory() as session:
            row = session.execute(sa.select(table).where(
                table.c.id == target_id, table.c.owner_id == owner_id,
                table.c.lifecycle_state == "active",
            )).mappings().one_or_none()
        if row is None:
            raise BrainError("NOT_FOUND")
        if self._storage is None:
            raise BrainError("DEPENDENCY_CONFLICT")
        if row["target_type"] != "asset" or row["kind"] not in {"extracted_text", "transcript", "description"}:
            raise BrainError("DEPENDENCY_CONFLICT")
        try:
            text = self._storage.read(row["payload_ref"]).decode("utf-8").strip()
        except (UnicodeDecodeError, OSError) as error:
            raise BrainError("DEPENDENCY_CONFLICT") from error
        if not text:
            raise BrainError("NOT_FOUND")
        return self._entry(
            "derived_content", target_id, "asset", row.get("sensitivity", "normal"),
            "derived", "fresh", text,
            [f"derived_content:{target_id}", f"asset:{row['source_id']}"],
        )

    def _raw_input(self, owner_id: UUID, target_id: UUID) -> dict[str, Any]:
        raw, intake = self._tables["raw_inputs"], self._tables["intake_requests"]
        with self._factory() as session:
            row = session.execute(sa.select(raw, intake.c.requested_scope).join(
                intake, intake.c.id == raw.c.intake_request_id,
            ).where(raw.c.id == target_id, raw.c.owner_id == owner_id,
                    raw.c.lifecycle_state == "active")).mappings().one_or_none()
        if row is None or not (row["content_text"] or "").strip():
            # A whitespace-only note has nothing to index (the boundary now
            # rejects new ones, but historic rows exist): treat it as "no source",
            # so the job settles as a declared skip instead of dead-lettering on
            # the embedder's blank-input rejection.
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
            conditions = [table.c.id == target_id, table.c.owner_id == owner_id]
            if "lifecycle_state" in table.c:
                # A tombstoned project (or task/checkpoint under it) is gone for
                # retrieval: a late bootstrap job must not recreate its card.
                conditions.append(table.c.lifecycle_state == "active")
            row = session.execute(sa.select(table).where(*conditions)).mappings().one_or_none()
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
            # Children of a deleted project are gone for retrieval: tasks,
            # checkpoints and observations carry no lifecycle_state of their own,
            # so the parent project is their only gate.
            parent_state = session.scalar(sa.select(self._tables["projects"].c.lifecycle_state).where(
                self._tables["projects"].c.id == UUID(str(project_id)),
                self._tables["projects"].c.owner_id == owner_id,
            ))
            if parent_state != "active":
                raise BrainError("NOT_FOUND")
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
