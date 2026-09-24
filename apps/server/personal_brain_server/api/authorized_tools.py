"""Production tool boundary: credentials in, persisted authority out.

Unlike the explicitly test-only helpers in ``life_tools``, this service accepts
neither a caller-selected client id nor caller-supplied permission grants.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any, Callable
from uuid import UUID

from personal_brain_domain.records.expenses import validate_money
from personal_brain_infra.persistence.authoritative_store import AuthoritativeStore
from personal_brain_infra.security.authority import PersistedAuthority
from personal_brain_infra.storage.base import StorageBackend
from personal_brain_infra.models.gateway import ModelGateway, ProviderCallBudget
from personal_brain_domain.common.errors import BrainError

# Must mirror the DB check constraints (self_category_allowed /
# review_item_type_allowed) so invalid values fail with a structured
# VALIDATION_FAILED instead of leaking an IntegrityError as HTTP 500.
SELF_CLAIM_CATEGORIES = frozenset({
    "preference", "aesthetic", "value", "working_style",
    "communication_style", "interest", "habit", "goal", "philosophy",
})
REVIEW_ITEM_TYPES = frozenset({
    "ambiguity", "conflict", "merge_candidate", "profile_confirmation",
    "deletion_confirmation", "permission_change", "failed_reconciliation",
})


class AuthorizedToolService:
    def __init__(
        self,
        authority: PersistedAuthority,
        store_factory: Callable[..., AuthoritativeStore],
        storage: StorageBackend | None = None,
        search_factory: Callable[..., Any] | None = None,
        model_gateway: ModelGateway | None = None,
        embedding_provider: Any | None = None,
    ) -> None:
        self._authority = authority
        self._store_factory = store_factory
        self._storage = storage
        self._search_factory = search_factory
        self._model_gateway = model_gateway
        self._embedding_provider = embedding_provider

    def add_expense(
        self,
        *,
        credential: str,
        amount: str,
        currency: str,
        category: str,
        description: str,
        occurred_timezone: str,
        requested_scope: str,
        idempotency_key: UUID,
    ) -> dict[str, Any]:
        context = self._authority.authenticate(credential)
        self._authority.authorize(
            context, tool="finance.write", scope=requested_scope, sensitivity="private",
        )
        money = validate_money(Decimal(amount), currency=currency, kind="expense")
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        result = store.add_expense(
            amount=f"{money.amount:.4f}",
            currency=money.currency,
            category=category,
            description=description,
            occurred_timezone=occurred_timezone,
            requested_scope=requested_scope,
            idempotency_key=idempotency_key,
            source_text=f"{description} {money.amount:.4f} {money.currency}",
            pre_commit=lambda: self._authority.authorize(
                context, tool="finance.write", scope=requested_scope, sensitivity="private",
            ),
        )
        self._authority.authorize(
            context, tool="finance.write", scope=requested_scope, sensitivity="private",
        )
        return result

    def save_note(
        self, *, credential: str, content: str, requested_scope: str,
        idempotency_key: UUID, content_hash: str | None = None,
    ) -> dict[str, Any]:
        if not content or not content.strip():
            raise BrainError("VALIDATION_FAILED")
        context = self._authority.authenticate(credential)
        self._authority.authorize(
            context, tool="knowledge.write", scope=requested_scope, sensitivity="private",
        )
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        result = store.save_note(
            content=content, requested_scope=requested_scope, idempotency_key=idempotency_key,
            content_hash=content_hash,
            pre_commit=lambda: self._authority.authorize(
                context, tool="knowledge.write", scope=requested_scope, sensitivity="private",
            ),
        )
        self._authority.authorize(
            context, tool="knowledge.write", scope=requested_scope, sensitivity="private",
        )
        return result

    def add_todo(
        self, *, credential: str, content: str, requested_scope: str,
        idempotency_key: UUID, priority: int = 0,
    ) -> dict[str, Any]:
        if not content or not content.strip():
            raise BrainError("VALIDATION_FAILED")
        context = self._authority.authenticate(credential)
        self._authority.authorize(
            context, tool="todo.write", scope=requested_scope, sensitivity="private",
        )
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        result = store.add_todo(
            content=content, requested_scope=requested_scope, idempotency_key=idempotency_key,
            priority=priority,
            pre_commit=lambda: self._authority.authorize(
                context, tool="todo.write", scope=requested_scope, sensitivity="private",
            ),
        )
        self._authority.authorize(
            context, tool="todo.write", scope=requested_scope, sensitivity="private",
        )
        return result

    def list_todos(self, *, credential: str, requested_scope: str = "todo") -> dict[str, Any]:
        context = self._authority.authenticate(credential)
        recheck = lambda: self._authority.authorize(
            context, tool="todo.read", scope=requested_scope, sensitivity="private",
        )
        recheck()
        result = self._todo_records(context)
        recheck()
        return result

    def complete_todo(self, *, credential: str, todo_id: UUID, expected_version: int,
                      idempotency_key: UUID, requested_scope: str = "todo") -> dict[str, Any]:
        context = self._authority.authenticate(credential)
        recheck = lambda: self._authority.authorize(
            context, tool="todo.write", scope=requested_scope, sensitivity="private",
        )
        recheck()
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        result = store.complete_todo(
            todo_id=todo_id, expected_version=expected_version,
            idempotency_key=idempotency_key, pre_commit=recheck,
        )
        recheck()
        return result

    def list_expense_records(self, *, credential: str,
                             requested_scope: str = "finance") -> dict[str, Any]:
        context = self._authority.authenticate(credential)
        self._authority.authorize(context, tool="finance.read", scope=requested_scope, sensitivity="private")
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        result = {"expenses": store.list_expenses()}
        self._authority.authorize(context, tool="finance.read", scope=requested_scope, sensitivity="private")
        return result

    def get_expense_summary(self, *, credential: str, currency: str | None = None,
                            requested_scope: str = "finance") -> dict[str, Any]:
        context = self._authority.authenticate(credential)
        recheck = lambda: self._authority.authorize(
            context, tool="finance.read", scope=requested_scope, sensitivity="private",
        )
        recheck()
        result = self._expense_summary(context, currency=currency)
        recheck()
        return result

    def _expense_summary(self, context: Any, *, currency: str | None = None) -> dict[str, Any]:
        """Exact per-currency totals for an already-authorized finance scope."""
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        return store.get_expense_summary(currency=currency)

    def _todo_records(self, context: Any) -> dict[str, Any]:
        """Exact todo records for an already-authorized todo scope."""
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        return {"todos": store.list_todos()}

    def get_self_context(self, *, credential: str, categories: list[str] | None = None,
                         requested_scope: str = "self") -> dict[str, Any]:
        context = self._authority.authenticate(credential)
        self._authority.authorize(context, tool="self.read", scope=requested_scope, sensitivity="private")
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        result = store.get_self_context(categories=categories)
        self._authority.authorize(context, tool="self.read", scope=requested_scope, sensitivity="private")
        return result

    def _search_core(
        self, context: Any, *, query: str, requested_scope: str,
        sensitivity_ceiling: str, query_embedding: list[float] | None,
        vector_model_version: str | None, limit: int,
    ) -> dict[str, Any]:
        """Route and execute one already-authorized read over the requested scope.

        The caller has authorized the entry-point tool named by its contract
        (``search.read`` / ``context.read`` / ``project.read``) for this scope, so
        this core performs no additional grant check and never widens the scope.
        """
        if not query or not query.strip():
            raise BrainError("VALIDATION_FAILED")
        from personal_brain_domain.retrieval.router import classify_intent

        intent = classify_intent(query)
        if intent == "expense_total" and requested_scope == "finance":
            return {"authority": "exact", **self._expense_summary(context)}
        if intent == "todo_list" and requested_scope == "todo":
            return {"authority": "exact", **self._todo_records(context)}
        if self._search_factory is None:
            raise RuntimeError("search repository is not configured")
        repository = self._search_factory(owner_id=context.owner_id)
        semantic_status = "provided" if query_embedding is not None else "disabled"
        if query_embedding is None and self._embedding_provider is not None:
            try:
                query_embedding = self._embedding_provider.embed(query)
                vector_model_version = self._embedding_provider.model_version
                semantic_status = "generated"
            except BrainError:
                semantic_status = "unavailable"
        hits = repository.search(
            query=query, authorized_scope=requested_scope,
            sensitivity_ceiling=sensitivity_ceiling, query_embedding=query_embedding,
            vector_model_version=vector_model_version, limit=min(max(limit, 1), 50),
        )
        return {"authority": "hybrid", "query": query, "hits": hits,
                "semantic_status": semantic_status}

    def search_brain(
        self, *, credential: str, query: str, requested_scope: str,
        sensitivity_ceiling: str = "private", query_embedding: list[float] | None = None,
        vector_model_version: str | None = None, limit: int = 20,
    ) -> dict[str, Any]:
        context = self._authority.authenticate(credential)
        recheck = lambda: self._authority.authorize(
            context, tool="search.read", scope=requested_scope,
            sensitivity=sensitivity_ceiling,
        )
        recheck()
        result = self._search_core(
            context, query=query, requested_scope=requested_scope,
            sensitivity_ceiling=sensitivity_ceiling, query_embedding=query_embedding,
            vector_model_version=vector_model_version, limit=limit,
        )
        recheck()
        return result

    def answer_brain(
        self, *, credential: str, query: str, requested_scope: str,
        sensitivity_ceiling: str = "private", limit: int = 12,
    ) -> dict[str, Any]:
        """Answer only from permission-filtered Brain evidence using the configured LLM."""
        if self._model_gateway is None:
            raise BrainError("TOOL_DENIED")
        context = self._authority.authenticate(credential)
        recheck = lambda: self._authority.authorize(
            context, tool="knowledge.read", scope=requested_scope,
            sensitivity=sensitivity_ceiling,
        )
        recheck()
        evidence = self._search_core(
            context, query=query, requested_scope=requested_scope,
            sensitivity_ceiling=sensitivity_ceiling, query_embedding=None,
            vector_model_version=None, limit=min(max(limit, 1), 20),
        )
        sources = [{
            "excerpt": hit.get("excerpt", ""),
            "source_links": hit.get("source_links", []),
            "freshness": hit.get("freshness"),
            "warnings": hit.get("warnings", []),
        } for hit in evidence.get("hits", [])]
        if not sources:
            return {
                "answer": "没有找到足够的已授权知识来回答。",
                "sources": [], "model": None, "grounded": False,
            }
        recheck()
        result = self._model_gateway.execute(
            {
                "prompt": query,
                "system": "仅根据给定的个人知识库证据回答。不得补充未经证据支持的事实；证据不足时明确说明。",
                "max_tokens": 1200,
            },
            {"sources": sources}, sensitivity=sensitivity_ceiling,
            budget=ProviderCallBudget(max_calls=1),
        )
        recheck()
        return {
            "answer": result["text"], "sources": sources,
            "model": result.get("model"), "grounded": True,
            "semantic_status": evidence.get("semantic_status"),
        }

    def search_project(
        self, *, credential: str, project_id: UUID, query: str,
        sensitivity_ceiling: str = "private", query_embedding: list[float] | None = None,
        vector_model_version: str | None = None, limit: int = 20,
    ) -> dict[str, Any]:
        scope = f"project:{project_id}"
        context = self._authority.authenticate(credential)
        recheck = lambda: self._authority.authorize(
            context, tool="project.read", scope=scope,
            sensitivity=sensitivity_ceiling,
        )
        recheck()
        result = self._search_core(
            context, query=query, requested_scope=scope,
            sensitivity_ceiling=sensitivity_ceiling, query_embedding=query_embedding,
            vector_model_version=vector_model_version, limit=limit,
        )
        recheck()
        return result

    def get_brain_context(
        self, *, credential: str, intent: str, requested_scope: str,
        detail: str = "normal", budget: int = 6000,
    ) -> dict[str, Any]:
        ceilings = {"summary": 2000, "normal": 6000, "deep": 12000}
        ceiling = min(budget, ceilings.get(detail, 6000))
        context = self._authority.authenticate(credential)
        recheck = lambda: self._authority.authorize(
            context, tool="context.read", scope=requested_scope, sensitivity="private",
        )
        recheck()
        result = self._search_core(
            context, query=intent, requested_scope=requested_scope,
            sensitivity_ceiling="private", query_embedding=None,
            vector_model_version=None, limit=20,
        )
        if result["authority"] == "exact":
            recheck()
            return {"intent": intent, "authority": "exact", "current_state": result,
                    "warnings": [], "used_budget": len(str(result).encode("utf-8"))}
        selected, used, warnings = [], 0, []
        for hit in result["hits"]:
            size = len(str(hit).encode("utf-8"))
            if used + size > ceiling:
                break
            selected.append(hit)
            used += size
            warnings.extend(hit.get("warnings") or [])
        recheck()
        return {"intent": intent, "authority": "hybrid", "current_state": selected,
                "warnings": list(dict.fromkeys(warnings)), "used_budget": used}

    def get_operation_status(self, *, credential: str, operation_id: UUID) -> dict[str, Any]:
        context = self._authority.authenticate(credential)
        self._authority.authorize(
            context, tool="operation.read", scope="operations", sensitivity="normal",
        )
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        result = store.get_operation_status(operation_id)
        self._authority.authorize(
            context, tool="operation.read", scope="operations", sensitivity="normal",
        )
        return result

    def create_project(self, *, credential: str, name: str, purpose: str,
                       requested_scope: str, idempotency_key: UUID) -> dict[str, Any]:
        if not name or not name.strip() or not purpose or not purpose.strip():
            # An unnamed project cannot be indexed (blank text) or meaningfully
            # discovered; reject at the boundary instead of orphaning it.
            raise BrainError("VALIDATION_FAILED")
        context = self._authority.authenticate(credential)
        recheck = lambda: self._authority.authorize(
            context, tool="project.write", scope=requested_scope, sensitivity="private",
        )
        recheck()
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        result = store.create_project(name=name, purpose=purpose, requested_scope=requested_scope,
                                      idempotency_key=idempotency_key, pre_commit=recheck)
        recheck()
        # Creator self-grant (last, after the final recheck): without a
        # project:<id> scope grant the freshly created project would be an
        # orphan — visible to nobody, readable by nobody, deletable by nobody.
        # Performed after the recheck so the mid-request epoch bump does not
        # trip the policy's stale-epoch guard; the client re-authenticates on
        # its next request and holds the new epoch.
        grant = getattr(self._authority, "grant_project_scope", None)
        if grant is not None and result.get("project_id"):
            grant(context, project_id=UUID(result["project_id"]))
        return result

    def list_projects(self, *, credential: str) -> dict[str, Any]:
        """Discover the owner's projects (previously impossible: creation had
        no enumeration, so a client could never find what it had built)."""
        context = self._authority.authenticate(credential)
        recheck = lambda: self._authority.authorize(
            context, tool="project.read", scope="projects", sensitivity="private",
        )
        recheck()
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        result = store.list_projects()
        recheck()
        return result

    def start_task(self, *, credential: str, project_id: UUID, goal: str, revision: str,
                   dirty_state: bool, constraints: list[str], idempotency_key: UUID,
                   plan: str | None = None, affected_modules: list[str] | None = None) -> dict[str, Any]:
        context = self._authority.authenticate(credential)
        scope = f"project:{project_id}"
        recheck = lambda: self._authority.authorize(
            context, tool="project.write", scope=scope, sensitivity="private",
        )
        recheck()
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        result = store.start_project_task(
            project_id=project_id, goal=goal, revision=revision, dirty_state=dirty_state,
            constraints=constraints, idempotency_key=idempotency_key, plan=plan,
            affected_modules=affected_modules, pre_commit=recheck,
        )
        recheck()
        return result

    def checkpoint_task(self, *, credential: str, task_id: UUID, completed_work: str,
                        next_step: str, problems: str, revision: str | None = None,
                        requested_scope: str, idempotency_key: UUID,
                        dirty_files: list[str] | None = None, changed_files: list[str] | None = None,
                        decisions: list[str] | None = None,
                        verification_evidence: str | None = None) -> dict[str, Any]:
        context = self._authority.authenticate(credential)
        recheck = lambda: self._authority.authorize(
            context, tool="project.write", scope=requested_scope, sensitivity="private",
        )
        recheck()
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        result = store.checkpoint_project_task(
            task_id=task_id, completed_work=completed_work, next_step=next_step,
            problems=problems, revision=revision, idempotency_key=idempotency_key,
            dirty_files=dirty_files, changed_files=changed_files, decisions=decisions,
            verification_evidence=verification_evidence,
            pre_commit=recheck,
        )
        recheck()
        return result

    def sync_workspace(
        self, *, credential: str, project_id: UUID, approved_root_identity: str,
        root_proof: str,
        revision: str | None, branch_ref: str | None, dirty_state: bool | None,
        changed_paths: list[str], file_hashes: dict[str, str],
        modules: list[dict[str, Any]], bridge_client_id: str, idempotency_key: UUID,
    ) -> dict[str, Any]:
        context = self._authority.authenticate(credential)
        expected_proof = hashlib.sha256(approved_root_identity.encode("utf-8")).hexdigest()
        if not __import__("hmac").compare_digest(root_proof, expected_proof):
            from personal_brain_domain.common.errors import BrainError
            raise BrainError("WORKSPACE_BOUNDARY_VIOLATION")
        scope = f"project:{project_id}"
        self._authority.authorize(context, tool="project.write", scope=scope, sensitivity="private")
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        result = store.sync_workspace(
            project_id=project_id, approved_root_identity=approved_root_identity,
            revision=revision, branch_ref=branch_ref, dirty_state=dirty_state,
            changed_paths=changed_paths, file_hashes=file_hashes, modules=modules,
            bridge_client_id=bridge_client_id, idempotency_key=idempotency_key,
        )
        self._authority.authorize(context, tool="project.write", scope=scope, sensitivity="private")
        return result

    def get_project_context(self, *, credential: str, project_id: UUID) -> dict[str, Any]:
        context = self._authority.authenticate(credential)
        scope = f"project:{project_id}"
        self._authority.authorize(context, tool="project.read", scope=scope, sensitivity="private")
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        result = store.get_project_recovery(project_id)
        self._authority.authorize(context, tool="project.read", scope=scope, sensitivity="private")
        return result

    def get_active_task(self, *, credential: str, project_id: UUID) -> dict[str, Any]:
        recovery = self.get_project_context(credential=credential, project_id=project_id)
        return {"active_task": recovery["active_task"], "next_step": recovery["next_step"]}

    def get_recent_changes(self, *, credential: str, project_id: UUID) -> dict[str, Any]:
        recovery = self.get_project_context(credential=credential, project_id=project_id)
        return {"change_events": recovery["change_events"], "workspace_evidence": recovery["workspace_evidence"]}

    def check_freshness(self, *, credential: str, project_id: UUID) -> dict[str, Any]:
        recovery = self.get_project_context(credential=credential, project_id=project_id)
        stale = [module for module in recovery["modules"] if module["freshness"] != "fresh"]
        return {"fresh": not stale, "modules": recovery["modules"], "warnings": stale}

    def get_module_context(self, *, credential: str, project_id: UUID, module_name: str) -> dict[str, Any]:
        recovery = self.get_project_context(credential=credential, project_id=project_id)
        for module in recovery["modules"]:
            if module["name"] == module_name:
                return {"module": module, "workspace_evidence": recovery["workspace_evidence"]}
        from personal_brain_domain.common.errors import BrainError
        raise BrainError("NOT_FOUND")

    def record_decision(self, *, credential: str, project_id: UUID, statement: str,
                        rationale: str, affected_modules: list[str],
                        idempotency_key: UUID) -> dict[str, Any]:
        return self._record_project_fact(
            credential=credential, project_id=project_id, kind="decision", statement=statement,
            rationale=rationale, affected_modules=affected_modules, idempotency_key=idempotency_key,
        )

    def record_constraint(self, *, credential: str, project_id: UUID, statement: str,
                          rationale: str, affected_modules: list[str],
                          idempotency_key: UUID) -> dict[str, Any]:
        return self._record_project_fact(
            credential=credential, project_id=project_id, kind="constraint", statement=statement,
            rationale=rationale, affected_modules=affected_modules, idempotency_key=idempotency_key,
        )

    def _record_project_fact(self, *, credential: str, project_id: UUID, kind: str,
                             statement: str, rationale: str, affected_modules: list[str],
                             idempotency_key: UUID) -> dict[str, Any]:
        context = self._authority.authenticate(credential)
        scope = f"project:{project_id}"
        recheck = lambda: self._authority.authorize(
            context, tool="project.write", scope=scope, sensitivity="private",
        )
        recheck()
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        result = store.record_project_fact(
            kind=kind, project_id=project_id, statement=statement, rationale=rationale,
            affected_modules=affected_modules, idempotency_key=idempotency_key, pre_commit=recheck,
        )
        recheck()
        return result

    def finalize_task(self, *, credential: str, task_id: UUID, outcome: str,
                      verification: str, remaining_work: str, end_revision: str | None = None,
                      end_dirty_state: bool | None = None, changed_files: list[str],
                      requested_scope: str, idempotency_key: UUID) -> dict[str, Any]:
        context = self._authority.authenticate(credential)
        recheck = lambda: self._authority.authorize(
            context, tool="project.write", scope=requested_scope, sensitivity="private",
        )
        recheck()
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        result = store.finalize_project_task(
            task_id=task_id, outcome=outcome, verification=verification,
            remaining_work=remaining_work, end_revision=end_revision,
            end_dirty_state=end_dirty_state, changed_files=changed_files,
            idempotency_key=idempotency_key, pre_commit=recheck,
        )
        recheck()
        return result

    def propose_self_claim(self, *, credential: str, category: str, claim_text: str,
                           policy_class: str, requested_scope: str,
                           idempotency_key: UUID) -> dict[str, Any]:
        if category not in SELF_CLAIM_CATEGORIES:
            raise BrainError("VALIDATION_FAILED")
        context = self._authority.authenticate(credential)
        recheck = lambda: self._authority.authorize(
            context, tool="self.write", scope=requested_scope, sensitivity="private",
        )
        recheck()
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        result = store.propose_self_claim(
            category=category, claim_text=claim_text, policy_class=policy_class,
            requested_scope=requested_scope, idempotency_key=idempotency_key, pre_commit=recheck,
        )
        recheck()
        return result

    def create_review_item(self, *, credential: str, item_type: str, subject_refs: list[str],
                           proposal: dict[str, Any], requested_scope: str,
                           idempotency_key: UUID) -> dict[str, Any]:
        if item_type not in REVIEW_ITEM_TYPES:
            raise BrainError("VALIDATION_FAILED")
        context = self._authority.authenticate(credential)
        recheck = lambda: self._authority.authorize(
            context, tool="review.write", scope=requested_scope, sensitivity="private",
        )
        recheck()
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        result = store.create_review_item(
            item_type=item_type, subject_refs=subject_refs, proposal=proposal,
            requested_scope=requested_scope, idempotency_key=idempotency_key, pre_commit=recheck,
        )
        recheck()
        return result

    def list_review_items(self, *, credential: str, state: str = "open") -> dict[str, Any]:
        context = self._authority.authenticate(credential)
        self._authority.authorize(
            context, tool="review.read", scope="review", sensitivity="private",
        )
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        result = {"items": store.list_review_items(state=state)}
        self._authority.authorize(
            context, tool="review.read", scope="review", sensitivity="private",
        )
        return result

    def resolve_review_item(self, *, credential: str, item_id: UUID, expected_version: int,
                            decision: str, idempotency_key: UUID) -> dict[str, Any]:
        context = self._authority.authenticate(credential)
        # ER-06 without the old circularity: this call *is* the confirmation, and
        # its proof is the version-bound single-use review item (15-minute expiry,
        # owner-bound resolver) which the store consumes transactionally. Raising
        # CONFIRMATION_REQUIRED here would demand a confirmation to confirm — the
        # loop could never close. Ordinary risk keeps the permission check.
        recheck = lambda: self._authority.authorize(
            context, tool="review.write", scope="review", sensitivity="private",
        )
        recheck()
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        result = store.resolve_review_item(
            item_id=item_id, expected_version=expected_version, decision=decision,
            idempotency_key=idempotency_key, pre_commit=recheck,
        )
        recheck()
        return result

    def create_deletion_plan(self, *, credential: str, targets: list[list[str]],
                             dependents: dict[str, list[list[str]]], requested_scope: str,
                             idempotency_key: UUID) -> dict[str, Any]:
        context = self._authority.authenticate(credential)
        # ER-06: proposing a plan destroys nothing — it persists a preview plus a
        # version-bound, single-use confirmation item with a 15-minute expiry. The
        # confirmation gate is therefore answered *with* the pending plan (D1:
        # "CONFIRMATION_REQUIRED + 计划详情"), not by refusing to create it; the
        # destructive execution happens only inside the approved-item path.
        recheck = lambda: self._authority.authorize(
            context, tool="review.write", scope=requested_scope, sensitivity="private",
        )
        recheck()
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        parsed_targets = [(str(t), UUID(str(i))) for t, i in targets]
        parsed_dependents = {UUID(str(key)): [(str(t), UUID(str(i))) for t, i in deps]
                             for key, deps in dependents.items()}
        result = store.create_deletion_plan(
            targets=parsed_targets, dependents=parsed_dependents,
            requested_scope=requested_scope, idempotency_key=idempotency_key, pre_commit=recheck,
        )
        recheck()
        return {
            **result, "confirmation_required": True,
            "confirmation_hint": (
                "review the pending deletion_confirmation item and approve it with "
                "resolve_review_item(item_id=review_item_id, expected_version=1, decision=approved)"
            ),
        }

    def get_deletion_plan(self, *, credential: str, plan_id: UUID) -> dict[str, Any]:
        context = self._authority.authenticate(credential)
        self._authority.authorize(
            context, tool="review.read", scope="review", sensitivity="private",
        )
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        result = store.get_deletion_plan(plan_id)
        self._authority.authorize(
            context, tool="review.read", scope="review", sensitivity="private",
        )
        return result

    def upload_asset(self, *, credential: str, content: bytes, original_name: str,
                     media_type: str, source_id: UUID, idempotency_key: UUID) -> dict[str, Any]:
        if self._storage is None:
            raise RuntimeError("asset storage is not configured")
        context = self._authority.authenticate(credential)
        recheck = lambda: self._authority.authorize(
            context, tool="asset.write", scope="asset", sensitivity="private",
        )
        recheck()
        store = self._store_factory(owner_id=context.owner_id, client_id=context.client_id)
        result = store.upload_asset(
            content=content, original_name=original_name, media_type=media_type,
            source_id=source_id, idempotency_key=idempotency_key,
            storage=self._storage, pre_commit=recheck,
        )
        recheck()
        return result
