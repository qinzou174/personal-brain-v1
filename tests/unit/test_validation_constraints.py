"""Red-first common model and request-envelope boundaries (ER-01, data-model)."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError


DOCUMENTED_ENUMS = {
    "sensitivity": {"normal", "personal", "private", "highly_private"},
    "information_class": {"fact", "explicit_user_statement", "observation", "ai_extraction", "ai_inference"},
    "canonicality": {"canonical", "derived"},
    "source_kind": {"explicit_user_statement", "original_document", "system_fact", "observation", "ai_extraction", "ai_inference"},
    "client_status": {"active", "suspended", "revoked"},
    "grant_effect": {"allow", "deny"},
    "intake_level": {"L0", "L1", "L2", "L3"},
    "intake_state": {"received", "accepted", "pending_confirmation", "processing", "completed", "rejected", "failed"},
    "derivation_role": {"extracted_from", "summarized_from", "embedded_from", "inferred_from", "supported_by", "contradicts"},
    "asset_integrity": {"unknown", "valid", "missing", "corrupted", "hash_mismatch"},
    "asset_processing": {"stored", "queued", "processing", "ready", "partial", "failed"},
    "derived_kind": {"extracted_text", "summary", "embedding", "description", "transcript", "digest", "archive_listing"},
    "derived_state": {"candidate", "active", "superseded", "failed", "orphaned", "recomputing"},
    "todo_state": {"pending", "in_progress", "completed", "cancelled"},
    "expense_kind": {"expense", "refund", "adjustment"},
    "entity_type": {"person", "place", "project", "concept", "media", "device", "organization", "extensible"},
    "memory_lifecycle": {"candidate", "active", "temporary", "historical", "superseded", "expired", "archived", "deleted"},
    "self_category": {"preference", "aesthetic", "value", "working_style", "communication_style", "interest", "habit", "goal", "philosophy"},
    "self_policy_class": {"A", "B", "C"},
    "self_establishment": {"candidate", "established", "explicit"},
    "self_review": {"none", "pending_confirmation", "rejected"},
    "evidence_stance": {"supports", "contradicts", "neutral"},
    "conflict_state": {"open", "resolved_by_time", "resolved_by_user", "tolerated", "superseded"},
    "module_freshness": {"fresh", "stale", "unknown"},
    "project_task_state": {"planned", "active", "paused", "completed", "failed", "cancelled"},
    "context_detail": {"summary", "normal", "deep"},
    "review_item_type": {"ambiguity", "conflict", "merge_candidate", "profile_confirmation", "deletion_confirmation", "permission_change", "failed_reconciliation"},
    "review_item_state": {"open", "approved", "rejected", "deferred", "resolved"},
    "job_state": {"queued", "leased", "succeeded", "retry_wait", "dead_letter", "cancelled"},
    "notification_state": {"candidate", "suppressed", "queued", "delivered", "failed", "acknowledged"},
    "health_component_state": {"healthy", "degraded", "failed", "unknown"},
}


BOUNDED_INPUTS = {
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


LIFE_MEMORY_FIELD_CONTRACTS = {
    "expense": (
        {"owner_id", "source_id", "amount", "currency", "kind", "category", "description", "occurred_at", "occurred_timezone", "lifecycle_state"},
        {"event_id"},
    ),
    "todo": (
        {"owner_id", "source_id", "content", "state", "priority"},
        {"due_at", "due_timezone", "due_window_start", "due_window_end", "completed_at", "archived_at"},
    ),
    "event": (
        {"owner_id", "source_id", "event_type", "title", "objective_description", "importance", "lifecycle_state"},
        {"subjective_experience_id", "parent_event_id", "start_at", "end_at"},
    ),
    "experience": (
        {"owner_id", "source_id", "event_id", "user_expression", "context"},
        {"normalized_interpretation", "confidence", "valid_from", "valid_to"},
    ),
    "entity": (
        {"owner_id", "source_id", "entity_type", "canonical_name", "aliases", "lifecycle_state"},
        {"confidence"},
    ),
    "relation": (
        {"owner_id", "source_id", "subject_type", "subject_id", "predicate", "object_type", "object_id", "lifecycle_state"},
        {"confidence", "valid_from", "valid_to"},
    ),
    "memory": (
        {"owner_id", "source_id", "kind", "statement", "lifecycle_state", "retention_policy"},
        {"confidence", "valid_from", "valid_to", "superseded_by_id"},
    ),
    "self_claim": (
        {"owner_id", "source_id", "category", "claim", "policy_class", "lifecycle_state", "establishment", "review"},
        {"confirmation_identity", "confirmation_time", "valid_from", "valid_to"},
    ),
    "evidence": (
        {"owner_id", "source_id", "target_id", "source_type", "stance", "source_trust", "observed_at", "lifecycle_state"},
        {"context", "contribution"},
    ),
}


def test_logical_model_inventory_covers_every_data_model_entity_without_secret_values():
    from personal_brain_domain.common.types import ENTITY_FIELDS

    expected = {
        "owner", "client", "credential", "oauth_grant", "permission_grant", "intake_request", "raw_input", "derivation_edge",
        "document", "asset", "asset_blob", "derived_content", "search_index_entry", "expense", "todo", "event",
        "experience", "entity", "relation", "memory", "self_claim", "evidence", "conflict", "project", "module_card",
        "project_task", "checkpoint", "decision", "constraint", "change_event", "milestone", "workspace_observation",
        "context_request", "context_package", "review_inbox_item", "job", "audit_event", "deletion_plan", "backup_set",
        "restore_verification", "notification", "health_finding",
    }
    assert set(ENTITY_FIELDS) == expected
    assert all(fields for fields in ENTITY_FIELDS.values())
    assert all("credential_value" not in fields and "raw_token" not in fields for fields in ENTITY_FIELDS.values())
    for entity, (required, nullable) in LIFE_MEMORY_FIELD_CONTRACTS.items():
        assert required | nullable <= ENTITY_FIELDS[entity] | {"owner_id", "source_id", "valid_from", "valid_to"}


@pytest.mark.parametrize("entity,fields", LIFE_MEMORY_FIELD_CONTRACTS.items())
def test_life_memory_required_and_nullable_field_contracts(entity, fields):
    from personal_brain_domain.common.types import ENTITY_FIELD_CONTRACTS, validate_entity_fields

    required, nullable = fields
    contract = ENTITY_FIELD_CONTRACTS[entity]
    assert set(contract.required_fields) == required
    assert set(contract.nullable_fields) == nullable
    payload = {field: "synthetic" for field in required} | {field: None for field in nullable}
    assert validate_entity_fields(entity, payload) == payload
    required_only = {field: "synthetic" for field in required}
    assert validate_entity_fields(entity, required_only) == required_only
    for field in required:
        with pytest.raises(ValueError):
            validate_entity_fields(entity, {name: value for name, value in payload.items() if name != field})
        with pytest.raises(ValueError):
            validate_entity_fields(entity, payload | {field: None})


@pytest.mark.parametrize("name,maximum", BOUNDED_INPUTS.items())
def test_documented_upper_bounds_at_plus_minus_one(name, maximum):
    from personal_brain_domain.common.types import BOUNDED_INPUTS as runtime_limits, validate_bounded_input

    assert runtime_limits[name] == maximum
    assert validate_bounded_input(name, maximum - 1) == maximum - 1
    assert validate_bounded_input(name, maximum) == maximum
    with pytest.raises(ValueError):
        validate_bounded_input(name, maximum + 1)


@pytest.mark.parametrize("detail,ceiling", [("summary", 2_000), ("normal", 6_000), ("deep", 12_000)])
def test_context_budget_never_exceeds_detail_cap(detail, ceiling):
    from personal_brain_domain.common.types import effective_context_budget

    assert effective_context_budget(detail, ceiling - 1) == ceiling - 1
    assert effective_context_budget(detail, ceiling) == ceiling
    assert effective_context_budget(detail, ceiling + 1) == ceiling


def test_confirmation_and_credential_overlap_expiry_edges():
    from personal_brain_domain.security.clients import validate_rotation_overlap
    from personal_brain_domain.security.policy import validate_confirmation_expiry

    issued = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert validate_confirmation_expiry(issued, issued + timedelta(minutes=15))
    assert not validate_confirmation_expiry(issued, issued + timedelta(minutes=15, seconds=1))
    assert validate_rotation_overlap(issued, issued + timedelta(hours=24))
    assert not validate_rotation_overlap(issued, issued + timedelta(hours=24, seconds=1))


def test_job_lease_attempt_and_retry_policy_defaults():
    from personal_brain_infra.jobs.store import JobPolicy

    policy = JobPolicy()
    assert policy.lease_seconds == 60
    assert policy.heartbeat_seconds == 20
    assert policy.max_attempts == 5
    assert policy.retry_base_seconds == (5, 30, 120, 600)
    assert policy.jitter_fraction == 0.20
    assert policy.next_delay(attempt=1, jitter=0) == 5
    assert policy.next_delay(attempt=4, jitter=0) == 600
    assert policy.next_delay(attempt=1, jitter=1) <= 6
    assert policy.next_delay(attempt=1, jitter=-1) >= 4


def test_quarantine_and_archive_depth_defaults():
    from personal_brain_domain.common.types import INTAKE_DEFAULTS

    assert INTAKE_DEFAULTS["quarantine_hours"] == 24
    assert INTAKE_DEFAULTS["archive_recursive_depth"] == 0


def test_idempotency_key_is_random_uuid_not_freeform_or_missing():
    from personal_brain_domain.common.types import validate_idempotency_key

    assert validate_idempotency_key(str(uuid4())).version == 4
    for invalid in (None, "", "same-text-every-time", "00000000-0000-0000-0000-000000000000"):
        with pytest.raises(ValueError):
            validate_idempotency_key(invalid)


@pytest.mark.parametrize("name,values", DOCUMENTED_ENUMS.items())
def test_documented_enums_reject_undeclared_values(name, values):
    from personal_brain_domain.common.types import ENUM_VALUES, validate_enum

    assert set(ENUM_VALUES[name]) == values
    assert all(validate_enum(name, value) == value for value in values)
    with pytest.raises(ValueError):
        validate_enum(name, "not-a-declared-value")


@pytest.mark.parametrize("value", ["normal", "personal", "private", "highly_private"])
def test_persistable_sensitivity_enum(value):
    from personal_brain_domain.common.types import CanonicalMetadata

    record = CanonicalMetadata(owner_id=uuid4(), source_id=uuid4(), sensitivity=value, information_class="fact", source_kind="system_fact")
    assert record.sensitivity == value


@pytest.mark.parametrize("value", ["secret", "unknown", ""])
def test_secret_and_unknown_sensitivity_never_enter_ordinary_record(value):
    from personal_brain_domain.common.types import CanonicalMetadata

    with pytest.raises(ValidationError):
        CanonicalMetadata(owner_id=uuid4(), source_id=uuid4(), sensitivity=value, information_class="fact", source_kind="system_fact")


@pytest.mark.parametrize("missing", ["owner_id", "source_id", "sensitivity", "information_class", "source_kind"])
def test_required_authority_fields_reject_missing_and_null(missing):
    from personal_brain_domain.common.types import CanonicalMetadata

    fields = {"owner_id": uuid4(), "source_id": uuid4(), "sensitivity": "personal", "information_class": "fact", "source_kind": "system_fact"}
    fields.pop(missing)
    with pytest.raises(ValidationError):
        CanonicalMetadata(**fields)
    fields[missing] = None
    with pytest.raises(ValidationError):
        CanonicalMetadata(**fields)


def test_nullable_validity_means_unknown_not_epoch_zero():
    from personal_brain_domain.common.types import CanonicalMetadata

    base = {"owner_id": uuid4(), "source_id": uuid4(), "sensitivity": "personal", "information_class": "fact", "source_kind": "system_fact"}
    record = CanonicalMetadata(**base, valid_from=None, valid_to=None)
    assert record.valid_from is None and record.valid_to is None
    actual_epoch_event = CanonicalMetadata(**base, valid_from=datetime.fromtimestamp(0, timezone.utc))
    assert actual_epoch_event.valid_from == datetime.fromtimestamp(0, timezone.utc)
    with pytest.raises(ValidationError):
        CanonicalMetadata(**base, valid_from=datetime(2026, 1, 2, tzinfo=timezone.utc), valid_to=datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_metadata_creation_and_update_times_are_utc_not_naive():
    from datetime import timedelta

    from personal_brain_domain.common.types import CanonicalMetadata

    local_time = datetime(2026, 9, 23, 12, 0, tzinfo=timezone(timedelta(hours=8)))
    base = {"owner_id": uuid4(), "source_id": uuid4(), "sensitivity": "personal", "information_class": "fact", "source_kind": "system_fact"}
    record = CanonicalMetadata(**base, created_at=local_time, updated_at=local_time)
    assert record.created_at == datetime(2026, 9, 23, 4, 0, tzinfo=timezone.utc)
    assert record.updated_at.tzinfo == timezone.utc
    with pytest.raises(ValidationError):
        CanonicalMetadata(**base, created_at=datetime(2026, 9, 23, 12, 0))


@pytest.mark.parametrize("field,valid,invalid", [
    ("information_class", "ai_inference", "model_says_true"),
    ("source_kind", "original_document", "document_is_fact"),
    ("canonicality", "canonical", "derived"),
])
def test_authority_classification_enums(field, valid, invalid):
    from personal_brain_domain.common.types import CanonicalMetadata

    base = {"owner_id": uuid4(), "source_id": uuid4(), "sensitivity": "personal", "information_class": "fact", "source_kind": "system_fact"}
    assert getattr(CanonicalMetadata(**(base | {field: valid})), field) == valid
    with pytest.raises(ValidationError):
        CanonicalMetadata(**(base | {field: invalid}))


def test_identifiers_are_opaque_uuids_and_version_positive():
    from personal_brain_domain.common.types import CanonicalMetadata

    base = {"owner_id": uuid4(), "source_id": uuid4(), "sensitivity": "personal", "information_class": "fact", "source_kind": "system_fact"}
    with pytest.raises(ValidationError):
        CanonicalMetadata(**(base | {"owner_id": "owner-1"}))
    with pytest.raises(ValidationError):
        CanonicalMetadata(**(base | {"version": 0}))
    assert CanonicalMetadata(**(base | {"version": 1})).version == 1


def test_derived_requires_generator_and_live_source_edge():
    from personal_brain_domain.common.types import DerivedMetadata

    base = {"owner_id": uuid4(), "source_id": uuid4(), "sensitivity": "personal", "information_class": "ai_extraction", "source_kind": "ai_extraction", "generator_kind": "parser", "generator_version": "1", "source_edge_ids": [uuid4()]}
    assert DerivedMetadata(**base).canonicality == "derived"
    for change in ({"generator_version": None}, {"source_edge_ids": []}, {"canonicality": "canonical"}):
        with pytest.raises(ValidationError):
            DerivedMetadata(**(base | change))


def test_uncertain_derived_claim_requires_confidence_inputs():
    from personal_brain_domain.common.types import DerivedMetadata

    base = {"owner_id": uuid4(), "source_id": uuid4(), "sensitivity": "personal", "information_class": "ai_inference", "source_kind": "ai_inference", "generator_kind": "model", "generator_version": "1", "source_edge_ids": [uuid4()], "uncertain": True}
    with pytest.raises(ValidationError):
        DerivedMetadata(**base)
    assert DerivedMetadata(**(base | {"confidence": "low", "confidence_inputs": {"source_count": 1}})).confidence == "low"


@pytest.mark.parametrize("length,allowed", [(511, True), (512, True), (513, False)])
def test_title_limit_one_below_at_one_above(length, allowed):
    from personal_brain_domain.common.types import validate_title

    if allowed:
        assert validate_title("x" * length) == "x" * length
    else:
        with pytest.raises(ValueError):
            validate_title("x" * length)


@pytest.mark.parametrize("length,allowed", [(7999, True), (8000, True), (8001, False)])
def test_query_limit_one_below_at_one_above(length, allowed):
    from personal_brain_domain.common.types import validate_query

    if allowed:
        assert validate_query("x" * length) == "x" * length
    else:
        with pytest.raises(ValueError):
            validate_query("x" * length)


@pytest.mark.parametrize("size,allowed", [(1_048_575, True), (1_048_576, True), (1_048_577, False)])
def test_text_envelope_utf8_byte_limit(size, allowed):
    from personal_brain_domain.common.types import validate_text_envelope

    payload = "x" * size
    if allowed:
        assert validate_text_envelope(payload) == payload
    else:
        with pytest.raises(ValueError):
            validate_text_envelope(payload)


@pytest.mark.parametrize("limit,allowed", [(0, False), (1, True), (20, True), (100, True), (101, False)])
def test_pagination_limit_boundaries(limit, allowed):
    from personal_brain_domain.common.types import Pagination

    if allowed:
        assert Pagination(limit=limit).limit == limit
    else:
        with pytest.raises(ValidationError):
            Pagination(limit=limit)
    assert Pagination().limit == 20
