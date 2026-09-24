"""Authority, provenance, limits, and lifecycle primitives for V1.

These objects describe ordinary persisted content. Secret classification occurs
before persistence and is deliberately absent from ``Sensitivity``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal, Mapping
from uuid import RFC_4122, UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Sensitivity(StrEnum):
    NORMAL = "normal"
    PERSONAL = "personal"
    PRIVATE = "private"
    HIGHLY_PRIVATE = "highly_private"


class InformationClass(StrEnum):
    FACT = "fact"
    EXPLICIT_USER_STATEMENT = "explicit_user_statement"
    OBSERVATION = "observation"
    AI_EXTRACTION = "ai_extraction"
    AI_INFERENCE = "ai_inference"


class SourceKind(StrEnum):
    EXPLICIT_USER_STATEMENT = "explicit_user_statement"
    ORIGINAL_DOCUMENT = "original_document"
    SYSTEM_FACT = "system_fact"
    OBSERVATION = "observation"
    AI_EXTRACTION = "ai_extraction"
    AI_INFERENCE = "ai_inference"


class Canonicality(StrEnum):
    CANONICAL = "canonical"
    DERIVED = "derived"


ENUM_VALUES: Mapping[str, frozenset[str]] = {
    "sensitivity": frozenset(Sensitivity),
    "information_class": frozenset(InformationClass),
    "canonicality": frozenset(Canonicality),
    "source_kind": frozenset(SourceKind),
    "client_status": frozenset({"active", "suspended", "revoked"}),
    "grant_effect": frozenset({"allow", "deny"}),
    "intake_level": frozenset({"L0", "L1", "L2", "L3"}),
    "intake_state": frozenset({"received", "accepted", "pending_confirmation", "processing", "completed", "rejected", "failed"}),
    "derivation_role": frozenset({"extracted_from", "summarized_from", "embedded_from", "inferred_from", "supported_by", "contradicts"}),
    "asset_integrity": frozenset({"unknown", "valid", "missing", "corrupted", "hash_mismatch"}),
    "asset_processing": frozenset({"stored", "queued", "processing", "ready", "partial", "failed"}),
    "derived_kind": frozenset({"extracted_text", "summary", "embedding", "description", "transcript", "digest", "archive_listing"}),
    "derived_state": frozenset({"candidate", "active", "superseded", "failed", "orphaned", "recomputing"}),
    "todo_state": frozenset({"pending", "in_progress", "completed", "cancelled"}),
    "expense_kind": frozenset({"expense", "refund", "adjustment"}),
    "entity_type": frozenset({"person", "place", "project", "concept", "media", "device", "organization", "extensible"}),
    "memory_lifecycle": frozenset({"candidate", "active", "temporary", "historical", "superseded", "expired", "archived", "deleted"}),
    "self_category": frozenset({"preference", "aesthetic", "value", "working_style", "communication_style", "interest", "habit", "goal", "philosophy"}),
    "self_policy_class": frozenset({"A", "B", "C"}),
    "self_establishment": frozenset({"candidate", "established", "explicit"}),
    "self_review": frozenset({"none", "pending_confirmation", "rejected"}),
    "evidence_stance": frozenset({"supports", "contradicts", "neutral"}),
    "conflict_state": frozenset({"open", "resolved_by_time", "resolved_by_user", "tolerated", "superseded"}),
    "module_freshness": frozenset({"fresh", "stale", "unknown"}),
    "project_task_state": frozenset({"planned", "active", "paused", "completed", "failed", "cancelled"}),
    "context_detail": frozenset({"summary", "normal", "deep"}),
    "review_item_type": frozenset({"ambiguity", "conflict", "merge_candidate", "profile_confirmation", "deletion_confirmation", "permission_change", "failed_reconciliation"}),
    "review_item_state": frozenset({"open", "approved", "rejected", "deferred", "resolved"}),
    "job_state": frozenset({"queued", "leased", "succeeded", "retry_wait", "dead_letter", "cancelled"}),
    "notification_state": frozenset({"candidate", "suppressed", "queued", "delivered", "failed", "acknowledged"}),
    "health_component_state": frozenset({"healthy", "degraded", "failed", "unknown"}),
}


def validate_enum(name: str, value: str) -> str:
    if name not in ENUM_VALUES or value not in ENUM_VALUES[name]:
        raise ValueError("invalid declared enum value")
    return value


BOUNDED_INPUTS: Mapping[str, int] = {
    "title_chars": 512,
    "query_chars": 8_000,
    "text_envelope_bytes": 1_048_576,
    "upload_bytes": 100 * 1_048_576,
    "asset_name_chars": 255,
    "archive_listing_entries": 1_000,
    "archive_listing_seconds": 30,
    "archive_listing_bytes": 1_048_576,
    "archive_listing_name_chars": 512,
    "archive_expanded_bytes": 500 * 1_048_576,
    "archive_member_bytes": 100 * 1_048_576,
    "archive_members": 1_000,
    "archive_job_seconds": 60,
    "archive_expansion_ratio": 100,
    "offline_queue_entries": 1_000,
    "offline_queue_bytes": 100 * 1_048_576,
}

INTAKE_DEFAULTS: Mapping[str, int] = {"quarantine_hours": 24, "archive_recursive_depth": 0}
CONTEXT_BUDGETS: Mapping[str, int] = {"summary": 2_000, "normal": 6_000, "deep": 12_000}


def validate_bounded_input(name: str, value: int) -> int:
    if name not in BOUNDED_INPUTS or isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("invalid bounded input")
    if value < 0 or value > BOUNDED_INPUTS[name]:
        raise ValueError("input exceeds documented bound")
    return value


def effective_context_budget(detail: str, client_budget: int) -> int:
    if detail not in CONTEXT_BUDGETS or isinstance(client_budget, bool) or client_budget < 1:
        raise ValueError("invalid context budget")
    return min(client_budget, CONTEXT_BUDGETS[detail])


def _bounded_text(value: str, *, limit: int, byte_count: bool = False) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("text must be nonempty")
    length = len(value.encode("utf-8")) if byte_count else len(value)
    if length > limit:
        raise ValueError("text exceeds documented bound")
    return value


def validate_title(value: str) -> str:
    return _bounded_text(value, limit=BOUNDED_INPUTS["title_chars"])


def validate_query(value: str) -> str:
    return _bounded_text(value, limit=BOUNDED_INPUTS["query_chars"])


def validate_text_envelope(value: str) -> str:
    return _bounded_text(value, limit=BOUNDED_INPUTS["text_envelope_bytes"], byte_count=True)


def validate_idempotency_key(value: str | UUID | None) -> UUID:
    try:
        key = UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise ValueError("idempotency key must be an RFC 4122 UUIDv4") from None
    if key.version != 4 or key.variant != RFC_4122:
        raise ValueError("idempotency key must be an RFC 4122 UUIDv4")
    return key


def _require_aware(value: datetime | None, field: str) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError(f"{field} must be timezone-aware")
    return value


class ValidityInterval(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid_from: datetime | None = None
    valid_to: datetime | None = None

    @model_validator(mode="after")
    def check_interval(self):
        _require_aware(self.valid_from, "valid_from")
        _require_aware(self.valid_to, "valid_to")
        if self.valid_from is not None and self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to precedes valid_from")
        return self


class ConcurrencyVersion(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: int = Field(ge=1)

    def advance(self, expected_version: int) -> "ConcurrencyVersion":
        if expected_version != self.value:
            raise ValueError("version conflict")
        return ConcurrencyVersion(value=self.value + 1)


class LifecycleValue(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str
    state: str

    @model_validator(mode="after")
    def check_state(self):
        validate_enum(self.kind, self.state)
        return self


class CanonicalMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    owner_id: UUID
    source_id: UUID
    sensitivity: Sensitivity
    information_class: InformationClass
    source_kind: SourceKind
    canonicality: Literal["canonical"] = "canonical"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    lifecycle_state: str = "active"
    deleted_at: datetime | None = None
    version: int = Field(default=1, ge=1)

    @field_validator("created_at", "updated_at", "valid_from", "valid_to", "deleted_at")
    @classmethod
    def require_aware_datetime(cls, value: datetime | None, info):
        checked = _require_aware(value, info.field_name)
        if checked is not None and info.field_name in {"created_at", "updated_at"}:
            return checked.astimezone(timezone.utc)
        return checked

    @model_validator(mode="after")
    def check_temporal_order(self):
        if self.updated_at < self.created_at:
            raise ValueError("updated_at precedes created_at")
        if self.valid_from is not None and self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to precedes valid_from")
        return self


class DerivedMetadata(CanonicalMetadata):
    canonicality: Literal["derived"] = "derived"
    generator_kind: str = Field(min_length=1)
    generator_version: str = Field(min_length=1)
    derived_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_edge_ids: tuple[UUID, ...] = Field(min_length=1)
    uncertain: bool = False
    confidence: str | float | None = None
    confidence_inputs: dict[str, Any] | None = None

    @field_validator("derived_at")
    @classmethod
    def require_aware_derived_at(cls, value: datetime):
        return _require_aware(value, "derived_at").astimezone(timezone.utc)

    @model_validator(mode="after")
    def check_uncertainty(self):
        if self.uncertain and (self.confidence is None or not self.confidence_inputs):
            raise ValueError("uncertain derivation requires confidence and inputs")
        return self


class Pagination(BaseModel):
    model_config = ConfigDict(frozen=True)

    limit: int = Field(default=20, ge=1, le=100)


@dataclass(frozen=True)
class EntityFieldContract:
    required_fields: frozenset[str]
    nullable_fields: frozenset[str]


def _fields(names: str) -> frozenset[str]:
    return frozenset(names.split())


# Logical fields from data-model.md. This is a contract inventory, not a claim
# that physical tables or story-specific validators already exist.
ENTITY_FIELDS: Mapping[str, frozenset[str]] = {
    "owner": _fields("owner_id created_at updated_at"),
    "client": _fields("client_id display_name client_type status scopes allowed_tools permission_epoch created_at last_used_at revoked_at"),
    "credential": _fields("credential_id client_id verifier issued_at expires_at revoked_at overlap_deadline"),
    "oauth_grant": _fields("grant_id issuer oauth_client_id audience owner_id client_id scopes expires_at revoked_at"),
    "permission_grant": _fields("grant_id client_id effect scope_pattern tool_pattern sensitivity_ceiling effective_from effective_to issuer reason"),
    "intake_request": _fields("request_id client_id operation idempotency_key received_at content_ref detected_intent declared_intent requested_scope security_decision intake_level state outcome_refs correlation_id error_code"),
    "raw_input": _fields("raw_input_id content_ref asset_ref content_hash original_at original_timezone source_channel client_id language sensitivity retention_policy canonical_state"),
    "derivation_edge": _fields("edge_id source_type source_id derived_type derived_id role contribution_weight generator_version created_at"),
    "document": _fields("document_id raw_input_id asset_id title document_type canonical_text content_ref language source_metadata current_extraction_id retention"),
    "asset": _fields("asset_id blob_id original_name media_type size_bytes sha256 storage_backend storage_key source_id user_metadata capture_at location_evidence integrity_state processing_state retention"),
    "asset_blob": _fields("blob_id sha256 size_bytes storage_backend storage_key reference_count first_seen_at last_integrity_check_at"),
    "derived_content": _fields("derivation_id target_type target_id kind version generator_identity confidence payload storage_ref state created_at"),
    "search_index_entry": _fields("entry_id target_type target_id authorized_scope sensitivity canonicality valid_from valid_to freshness searchable_text vector_model_version metadata_filters indexed_at"),
    "expense": _fields("expense_id amount currency category description occurred_at occurred_timezone source_id event_id kind lifecycle_state"),
    "todo": _fields("todo_id content state due_at due_timezone due_window_start due_window_end due_precision priority created_at completed_at source_id archived_at"),
    "event": _fields("event_id event_type title objective_description subjective_experience_id start_at end_at event_timezone importance source_id confidence parent_event_id lifecycle_state"),
    "experience": _fields("experience_id event_id user_expression normalized_interpretation context source_id confidence valid_from valid_to"),
    "entity": _fields("entity_id entity_type canonical_name aliases source_id confidence lifecycle_state"),
    "relation": _fields("relation_id subject_type subject_id predicate object_type object_id source_id confidence valid_from valid_to lifecycle_state"),
    "memory": _fields("memory_id kind statement lifecycle_state source_class confidence confidence_inputs retention_policy valid_from valid_to context exceptions strength superseded_by_id"),
    "self_claim": _fields("self_claim_id category claim policy_class lifecycle_state establishment review correction_events confidence_inputs evidence_summary valid_from valid_to context exceptions confirmation_identity confirmation_time"),
    "evidence": _fields("evidence_id target_type target_id source_type source_id stance source_trust observed_at context contribution lifecycle_state"),
    "conflict": _fields("conflict_id participants conflict_type detected_at evidence state resolution resolver"),
    "project": _fields("project_id name purpose goals principles technology_summary architecture_summary deployment_summary global_constraints directory_overview workspace_identity repository_identity current_revision_evidence lifecycle_state"),
    "module_card": _fields("module_id project_id name paths responsibility core_files interfaces dependencies consumers constraints indexed_revision relevant_file_hashes freshness stale_reasons refreshed_at"),
    "project_task": _fields("task_id project_id goal state start_revision end_revision start_dirty_state end_dirty_state plan constraints affected_modules started_at completed_at remaining_work final_report"),
    "checkpoint": _fields("checkpoint_id task_id revision dirty_files changed_files completed_work problems decisions next_step verification_evidence captured_at"),
    "decision": _fields("decision_id project_id module_id task_id statement rationale evidence source_id valid_from valid_to lifecycle_state deduplication_key"),
    "constraint": _fields("constraint_id project_id module_id task_id statement rationale evidence source_id valid_from valid_to lifecycle_state deduplication_key"),
    "change_event": _fields("change_event_id project_id module_id task_id statement rationale evidence source_id valid_from valid_to lifecycle_state deduplication_key affected_modules revisions"),
    "milestone": _fields("milestone_id project_id module_id task_id statement rationale evidence source_id valid_from valid_to lifecycle_state deduplication_key"),
    "workspace_observation": _fields("observation_id project_id approved_root_identity revision branch_ref dirty_state changed_paths diff_summary file_hashes observed_at bridge_client_id"),
    "context_request": _fields("request_id client_id intent requested_scopes effective_scopes detail_level token_budget size_budget query target_project_id target_module_id time_start time_end correlation_id"),
    "context_package": _fields("package_id request_id intent current_state historical_rationale active_task relevant_objects decisions constraints recent_changes warnings suggested_next_actions source_references used_budget generated_at"),
    "review_inbox_item": _fields("item_id item_type subject_refs proposal risk evidence state resolver resolved_at"),
    "job": _fields("job_id job_type payload_ref idempotency_key state priority attempts max_attempts available_at lease_owner lease_expires_at started_at finished_at error_code error_summary result_refs"),
    "audit_event": _fields("audit_id client_id correlation_id action tool effective_scope target_category target_id outcome error_code duration_ms occurred_at risk authorization_decision"),
    "deletion_plan": _fields("plan_id requested_targets impact_graph policy_actions backup_implications risk created_at confirmation_state confirmation_identity confirmation_time execution_state reconciliation_state audit_ref"),
    "backup_set": _fields("backup_id inventory covered_revision covered_at database_artifact asset_manifest configuration_manifest retention_tier state integrity_result completed_at"),
    "restore_verification": _fields("verification_id backup_id isolated_target_id restored_record_counts relationship_checks permission_cases representative_queries asset_hashes result failures verified_at"),
    "notification": _fields("notification_id trigger_type source_object risk priority dedupe_key cooldown_group channel state reason created_at delivered_at"),
    "health_finding": _fields("finding_id component category severity status first_seen_at last_seen_at evidence_summary affected_objects remediation_guidance acknowledged_at resolved_at"),
}


ENTITY_FIELD_CONTRACTS: Mapping[str, EntityFieldContract] = {
    "expense": EntityFieldContract(frozenset({"owner_id", "source_id", "amount", "currency", "kind", "category", "description", "occurred_at", "occurred_timezone", "lifecycle_state"}), frozenset({"event_id"})),
    "todo": EntityFieldContract(frozenset({"owner_id", "source_id", "content", "state", "priority"}), frozenset({"due_at", "due_timezone", "due_window_start", "due_window_end", "completed_at", "archived_at"})),
    "event": EntityFieldContract(frozenset({"owner_id", "source_id", "event_type", "title", "objective_description", "importance", "lifecycle_state"}), frozenset({"subjective_experience_id", "parent_event_id", "start_at", "end_at"})),
    "experience": EntityFieldContract(frozenset({"owner_id", "source_id", "event_id", "user_expression", "context"}), frozenset({"normalized_interpretation", "confidence", "valid_from", "valid_to"})),
    "entity": EntityFieldContract(frozenset({"owner_id", "source_id", "entity_type", "canonical_name", "aliases", "lifecycle_state"}), frozenset({"confidence"})),
    "relation": EntityFieldContract(frozenset({"owner_id", "source_id", "subject_type", "subject_id", "predicate", "object_type", "object_id", "lifecycle_state"}), frozenset({"confidence", "valid_from", "valid_to"})),
    "memory": EntityFieldContract(frozenset({"owner_id", "source_id", "kind", "statement", "lifecycle_state", "retention_policy"}), frozenset({"confidence", "valid_from", "valid_to", "superseded_by_id"})),
    "self_claim": EntityFieldContract(frozenset({"owner_id", "source_id", "category", "claim", "policy_class", "lifecycle_state", "establishment", "review"}), frozenset({"confirmation_identity", "confirmation_time", "valid_from", "valid_to"})),
    "evidence": EntityFieldContract(frozenset({"owner_id", "source_id", "target_id", "source_type", "stance", "source_trust", "observed_at", "lifecycle_state"}), frozenset({"context", "contribution"})),
}


def validate_entity_fields(entity: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    if entity not in ENTITY_FIELD_CONTRACTS:
        raise ValueError("unknown entity contract")
    missing = ENTITY_FIELD_CONTRACTS[entity].required_fields - payload.keys()
    if missing or any(payload[field] is None for field in ENTITY_FIELD_CONTRACTS[entity].required_fields):
        raise ValueError("missing or null required entity field")
    return dict(payload)
