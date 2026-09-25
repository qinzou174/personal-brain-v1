"""Tool registry mapping protocol adapters to replaceable application operations.

FR-002/FR-098/FR-099: the registry declares the tool surface without duplicating
domain policy; adapters call these operations and the registry enforces no
domain rules beyond delegation.
"""

from __future__ import annotations

from typing import Mapping

# Compatibility-only synthetic handlers used by legacy unit journeys. The
# production runtime never resolves these; it binds AuthorizedToolService.
_LEGACY_TEST_TOOL_REGISTRY: Mapping[str, str] = {
    "save_note": "life_tools:save_note",
    "add_expense": "life_tools:add_expense",
    "get_expense_summary": "life_tools:get_expense_summary",
    "list_expense_records": "life_tools:list_expense_records",
    "add_todo": "life_tools:add_todo",
    "list_todos": "life_tools:list_todos",
    "complete_todo": "life_tools:complete_todo",
    "get_brain_context": "context_tools:get_brain_context",
    "search_brain": "context_tools:search_brain",
    "get_self_context": "context_tools:get_self_context",
    "get_project_context": "project_tools:get_recovery",
    "get_active_task": "project_tools:get_recovery",
    "start_task": "project_tools:start_task",
    "checkpoint_task": "project_tools:checkpoint_task",
    "upload_asset": "asset_tools:upload_asset",
}

FR099_TOOL_NAMES = frozenset({
    "get_brain_context", "search_brain", "answer_brain", "get_self_context", "get_expense_summary",
    "list_expense_records", "list_todos", "get_project_context", "get_module_context",
    "search_project", "get_active_task", "get_recent_changes", "check_freshness",
    "save_note", "add_expense", "add_todo", "complete_todo", "start_task",
    "checkpoint_task", "finalize_task", "record_decision", "record_constraint",
    "sync_workspace", "upload_asset", "get_operation_status", "create_project",
    "propose_self_claim", "create_review_item", "create_deletion_plan", "get_deletion_plan",
    # D1/D2 2026-09-25: without these two the governance loop could not close from
    # a client — a plan or merge candidate could be created but never seen or
    # approved. The surface grows 30 -> 32.
    "list_review_items", "resolve_review_item",
    # D-projects 2026-09-25: creation had no discovery — a client could never
    # enumerate the projects it had built. The surface grows 32 -> 33.
    "list_projects",
    # AI-consumer readability 2026-09-25: search could find a card but nothing
    # could read one in full (300-char head excerpt only). The surface grows
    # 33 -> 34; authorization reuses `search.read` on the entry's own scope.
    "get_entry_content",
})

_UUID = {"type": "string", "format": "uuid"}
_TEXT = {"type": "string", "minLength": 1}


def _schema(required: tuple[str, ...] = (), **properties: object) -> dict[str, object]:
    return {
        "type": "object", "properties": properties,
        "required": list(required), "additionalProperties": False,
    }


_TOOL_SCHEMAS: Mapping[str, dict[str, object]] = {
    "get_brain_context": _schema(("intent", "requested_scope"), intent=_TEXT, requested_scope=_TEXT,
                                 detail={"enum": ["summary", "normal", "deep"]}, budget={"type": "integer"}),
    "search_brain": _schema(("query", "requested_scope"), query=_TEXT, requested_scope=_TEXT,
                            sensitivity_ceiling={"enum": ["normal", "personal", "private", "highly_private"]},
                            query_embedding={"type": "array", "items": {"type": "number"}},
                            vector_model_version={"type": "string"}, limit={"type": "integer"}),
    "answer_brain": _schema(("query", "requested_scope"), query=_TEXT, requested_scope=_TEXT,
                             sensitivity_ceiling={"enum": ["normal", "personal", "private", "highly_private"]},
                             limit={"type": "integer", "minimum": 1, "maximum": 20}),
    "get_self_context": _schema(categories={"type": "array", "items": {"type": "string"}}, requested_scope=_TEXT),
    "get_expense_summary": _schema(currency={"type": "string"}, requested_scope=_TEXT),
    "list_expense_records": _schema(requested_scope=_TEXT),
    "list_todos": _schema(requested_scope=_TEXT),
    "get_project_context": _schema(("project_id",), project_id=_UUID),
    "get_module_context": _schema(("project_id", "module_name"), project_id=_UUID, module_name=_TEXT),
    "search_project": _schema(("project_id", "query"), project_id=_UUID, query=_TEXT,
                              sensitivity_ceiling={"type": "string"}, query_embedding={"type": "array", "items": {"type": "number"}},
                              vector_model_version={"type": "string"}, limit={"type": "integer"}),
    "get_active_task": _schema(("project_id",), project_id=_UUID),
    "get_recent_changes": _schema(("project_id",), project_id=_UUID),
    "check_freshness": _schema(("project_id",), project_id=_UUID),
    "save_note": _schema(("content", "requested_scope", "idempotency_key"), content=_TEXT, requested_scope=_TEXT,
                         idempotency_key=_UUID, content_hash={"type": "string", "pattern": "^[0-9a-f]{64}$"}),
    "add_expense": _schema(("amount", "currency", "category", "description", "occurred_timezone", "requested_scope", "idempotency_key"),
                           amount=_TEXT, currency=_TEXT, category=_TEXT, description=_TEXT, occurred_timezone=_TEXT,
                           requested_scope=_TEXT, idempotency_key=_UUID),
    "add_todo": _schema(("content", "requested_scope", "idempotency_key"), content=_TEXT, requested_scope=_TEXT,
                         idempotency_key=_UUID, priority={"type": "integer"}),
    "complete_todo": _schema(("todo_id", "expected_version", "idempotency_key"), todo_id=_UUID,
                              expected_version={"type": "integer", "minimum": 1}, idempotency_key=_UUID, requested_scope=_TEXT),
    "create_project": _schema(("name", "purpose", "requested_scope", "idempotency_key"), name=_TEXT, purpose=_TEXT,
                              requested_scope=_TEXT, idempotency_key=_UUID),
    "start_task": _schema(("project_id", "goal", "revision", "dirty_state", "constraints", "idempotency_key"),
                          project_id=_UUID, goal=_TEXT, revision=_TEXT, dirty_state={"type": "boolean"},
                          constraints={"type": "array", "items": {"type": "string"}}, idempotency_key=_UUID,
                          plan={"type": "string"}, affected_modules={"type": "array", "items": {"type": "string"}}),
    "checkpoint_task": _schema(("task_id", "completed_work", "next_step", "problems", "requested_scope", "idempotency_key"),
                               task_id=_UUID, completed_work=_TEXT, next_step=_TEXT, problems={"type": "string"}, revision={"type": ["string", "null"]},
                               requested_scope=_TEXT, idempotency_key=_UUID, dirty_files={"type": "array", "items": {"type": "string"}},
                               changed_files={"type": "array", "items": {"type": "string"}}, decisions={"type": "array", "items": {"type": "string"}},
                               verification_evidence={"type": "string"}),
    "finalize_task": _schema(("task_id", "outcome", "verification", "remaining_work", "changed_files", "requested_scope", "idempotency_key"),
                             task_id=_UUID, outcome=_TEXT, verification=_TEXT, remaining_work={"type": "string"},
                             end_revision={"type": ["string", "null"]}, end_dirty_state={"type": ["boolean", "null"]},
                             changed_files={"type": "array", "items": {"type": "string"}}, requested_scope=_TEXT, idempotency_key=_UUID),
    "record_decision": _schema(("project_id", "statement", "rationale", "affected_modules", "idempotency_key"),
                               project_id=_UUID, statement=_TEXT, rationale={"type": "string"},
                               affected_modules={"type": "array", "items": {"type": "string"}}, idempotency_key=_UUID),
    "record_constraint": _schema(("project_id", "statement", "rationale", "affected_modules", "idempotency_key"),
                                 project_id=_UUID, statement=_TEXT, rationale={"type": "string"},
                                 affected_modules={"type": "array", "items": {"type": "string"}}, idempotency_key=_UUID),
    "sync_workspace": _schema(("project_id", "approved_root_identity", "root_proof", "changed_paths", "file_hashes", "modules", "bridge_client_id", "idempotency_key"),
                              project_id=_UUID, approved_root_identity=_TEXT, root_proof=_TEXT, revision={"type": ["string", "null"]},
                              branch_ref={"type": ["string", "null"]}, dirty_state={"type": ["boolean", "null"]},
                              changed_paths={"type": "array", "items": {"type": "string"}}, file_hashes={"type": "object"},
                              modules={"type": "array", "items": {"type": "object"}}, bridge_client_id=_TEXT, idempotency_key=_UUID),
    "upload_asset": _schema(("content_base64", "original_name", "media_type", "source_id", "idempotency_key"),
                            content_base64=_TEXT, original_name=_TEXT, media_type=_TEXT, source_id=_UUID, idempotency_key=_UUID),
    "get_operation_status": _schema(("operation_id",), operation_id=_UUID),
    "propose_self_claim": _schema(("category", "claim_text", "policy_class", "requested_scope", "idempotency_key"),
                                  category={"enum": [
                                      "preference", "aesthetic", "value", "working_style",
                                      "communication_style", "interest", "habit", "goal", "philosophy",
                                  ]}, claim_text=_TEXT, policy_class={"enum": ["A", "B", "C"]},
                                  requested_scope=_TEXT, idempotency_key=_UUID),
    "create_review_item": _schema(("item_type", "subject_refs", "proposal", "requested_scope", "idempotency_key"),
                                  item_type={"enum": [
                                      "ambiguity", "conflict", "merge_candidate", "profile_confirmation",
                                      "deletion_confirmation", "permission_change", "failed_reconciliation",
                                  ]}, subject_refs={"type": "array", "items": {"type": "string"}},
                                  proposal={"type": "object"}, requested_scope=_TEXT, idempotency_key=_UUID),
    "create_deletion_plan": _schema(("targets", "dependents", "requested_scope", "idempotency_key"),
                                    targets={"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
                                    dependents={"type": "object",
                                                "additionalProperties": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}}},
                                    requested_scope=_TEXT, idempotency_key=_UUID),
    "get_deletion_plan": _schema(("plan_id",), plan_id=_UUID),
    "list_review_items": _schema(
        state={"enum": ["open", "deferred", "approved", "rejected"]},
    ),
    "resolve_review_item": _schema(("item_id", "expected_version", "decision", "idempotency_key"),
                                   item_id=_UUID, expected_version={"type": "integer", "minimum": 1},
                                   decision={"enum": ["approved", "rejected"]}, idempotency_key=_UUID),
    "list_projects": _schema(),
    "get_entry_content": _schema(("entry_id",), entry_id=_UUID,
                                 sensitivity_ceiling={"enum": ["normal", "personal", "private", "highly_private"]}),
}


def list_tool_names() -> list[str]:
    return sorted(FR099_TOOL_NAMES)


def tool_definitions() -> list[dict[str, object]]:
    """Return stable discovery metadata; detailed validation remains in services."""
    return [
        {
            "name": name,
            "description": f"Personal Brain operation: {name}",
            "inputSchema": _TOOL_SCHEMAS[name],
        }
        for name in sorted(FR099_TOOL_NAMES)
    ]


def resolve_tool(name: str):
    """Resolve a tool name to its application function (lazy import, no policy here)."""
    if name not in _LEGACY_TEST_TOOL_REGISTRY:
        raise KeyError(f"unknown tool: {name}")
    module_name, function_name = _LEGACY_TEST_TOOL_REGISTRY[name].split(":")
    import importlib

    module = importlib.import_module(f"personal_brain_server.api.{module_name}")
    return getattr(module, function_name)
