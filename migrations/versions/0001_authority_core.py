"""Authority, intake, audit, idempotency, job and derivation core only.

This revision intentionally creates no Expense, Todo, Memory, Project, Asset,
SearchIndex or Notification table. Later numbered migrations add those once.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0001_authority_core"
down_revision = None
branch_labels = None
depends_on = None

SOURCE_VERSION = "empty"
TARGET_VERSION = revision
AFFECTED_CANONICAL = (
    "Owner", "Client", "Credential", "OAuthGrant", "PermissionGrant", "IntakeRequest",
    "RawInput", "AuditEvent", "Idempotency", "Job", "DerivationEdge", "ReviewInboxItem",
)
AFFECTED_DERIVED = ("DerivedContent",)
LOCK_STORAGE_IMPACT = "Initial empty-schema create; 13 tables, unique indexes and foreign keys; no existing canonical rows rewritten."
BACKUP_PREREQUISITE = "Empty synthetic database only; any populated target requires an independently verified restore point before migration."
RESTORE_STRATEGY = "Production rollback is restore from the verified pre-migration backup; downgrade is restricted to isolated brain_migration_test_* schemas."
PREFLIGHT_SQL = "SELECT current_schema() IS NOT NULL AS schema_selected"

CREATED_TABLES = (
    "owners", "clients", "credentials", "oauth_grants", "permission_grants",
    "intake_requests", "raw_inputs", "audit_events", "idempotency_records",
    "jobs", "derivation_edges", "derived_contents", "review_inbox_items",
)
POST_VALIDATION_SQL = (
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = current_schema() "
    "AND table_name IN (" + ",".join("'" + name + "'" for name in CREATED_TABLES) + ")"
)

SENSITIVITY = "'normal','personal','private','highly_private'"
INFORMATION_CLASS = "'fact','explicit_user_statement','observation','ai_extraction','ai_inference'"
SOURCE_KIND = "'explicit_user_statement','original_document','system_fact','observation','ai_extraction','ai_inference'"


def _id():
    return sa.Column("id", UUID(as_uuid=True), primary_key=True)


def _owner():
    return sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("owners.id", ondelete="RESTRICT"), nullable=False)


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def _version():
    return sa.Column("version", sa.Integer(), nullable=False, server_default="1")


def _information():
    return (
        sa.Column("sensitivity", sa.String(32), nullable=False),
        sa.Column("information_class", sa.String(32), nullable=False),
        sa.Column("canonicality", sa.String(16), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("lifecycle_state", sa.String(32), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(f"sensitivity IN ({SENSITIVITY})", name="sensitivity_allowed"),
        sa.CheckConstraint(f"information_class IN ({INFORMATION_CLASS})", name="information_class_allowed"),
        sa.CheckConstraint(f"source_kind IN ({SOURCE_KIND})", name="source_kind_allowed"),
        sa.CheckConstraint("valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from", name="valid_interval_order"),
    )


def upgrade() -> None:
    op.create_table(
        "owners", _id(), *_timestamps(), _version(),
        sa.CheckConstraint("version >= 1", name="owner_version_positive"),
    )
    op.create_table(
        "clients", _id(), _owner(),
        sa.Column("display_name", sa.String(512), nullable=False),
        sa.Column("client_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("scopes", JSONB, nullable=False),
        sa.Column("allowed_tools", JSONB, nullable=False),
        sa.Column("permission_epoch", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        *_timestamps(), _version(),
        sa.CheckConstraint("status IN ('active','suspended','revoked')", name="client_status_allowed"),
        sa.CheckConstraint("permission_epoch >= 0", name="permission_epoch_nonnegative"),
    )
    op.create_table(
        "credentials", _id(),
        sa.Column("client_id", UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("verifier", sa.Text(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("overlap_deadline", sa.DateTime(timezone=True)),
        *_timestamps(), _version(),
        sa.CheckConstraint("length(verifier) > 0", name="verifier_nonempty"),
        sa.CheckConstraint("expires_at IS NULL OR expires_at > issued_at", name="credential_expiry_order"),
        sa.CheckConstraint("overlap_deadline IS NULL OR overlap_deadline <= issued_at + interval '24 hours'", name="rotation_overlap_max"),
    )
    op.create_table(
        "oauth_grants", _id(), _owner(),
        sa.Column("client_id", UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("issuer", sa.Text(), nullable=False),
        sa.Column("oauth_client_id", sa.Text(), nullable=False),
        sa.Column("audience", sa.Text(), nullable=False),
        sa.Column("scopes", JSONB, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        *_timestamps(), _version(),
    )
    op.create_table(
        "permission_grants", _id(),
        sa.Column("client_id", UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("effect", sa.String(8), nullable=False),
        sa.Column("scope_pattern", sa.String(256), nullable=False),
        sa.Column("tool_pattern", sa.String(256), nullable=False),
        sa.Column("sensitivity_ceiling", sa.String(32), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True)),
        sa.Column("issuer", sa.String(128), nullable=False),
        sa.Column("reason", sa.String(1024)),
        *_timestamps(), _version(),
        sa.CheckConstraint("effect IN ('allow','deny')", name="grant_effect_allowed"),
        sa.CheckConstraint(f"sensitivity_ceiling IN ({SENSITIVITY})", name="grant_sensitivity_allowed"),
        sa.CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="grant_interval_order"),
    )
    op.create_table(
        "intake_requests", _id(), _owner(),
        sa.Column("client_id", UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("operation", sa.String(128), nullable=False),
        sa.Column("idempotency_key", UUID(as_uuid=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_ref", sa.Text()),
        sa.Column("detected_intent", sa.String(128)),
        sa.Column("declared_intent", sa.String(128)),
        sa.Column("requested_scope", sa.String(256), nullable=False),
        sa.Column("security_decision", sa.String(32), nullable=False),
        sa.Column("intake_level", sa.String(2), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("outcome_refs", JSONB, nullable=False),
        sa.Column("correlation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("error_code", sa.String(64)),
        *_timestamps(), _version(),
        sa.UniqueConstraint("client_id", "operation", "idempotency_key", name="uq_intake_idempotency"),
        sa.CheckConstraint("intake_level IN ('L0','L1','L2','L3')", name="intake_level_allowed"),
        sa.CheckConstraint("state IN ('received','accepted','pending_confirmation','processing','completed','rejected','failed')", name="intake_state_allowed"),
    )
    op.create_table(
        "raw_inputs", _id(), _owner(),
        sa.Column("intake_request_id", UUID(as_uuid=True), sa.ForeignKey("intake_requests.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("client_id", UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("content_text", sa.Text()),
        sa.Column("asset_ref", sa.Text()),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("original_at", sa.DateTime(timezone=True)),
        sa.Column("original_timezone", sa.String(64)),
        sa.Column("source_channel", sa.String(64), nullable=False),
        sa.Column("language", sa.String(32)),
        sa.Column("retention_policy", sa.String(64), nullable=False),
        *_information(), *_timestamps(), _version(),
        sa.CheckConstraint("canonicality = 'canonical'", name="raw_canonical_only"),
        sa.CheckConstraint("content_text IS NOT NULL OR asset_ref IS NOT NULL", name="raw_content_present"),
    )
    op.create_table(
        "audit_events", _id(), _owner(),
        sa.Column("client_id", UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="SET NULL")),
        sa.Column("correlation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("tool", sa.String(128)),
        sa.Column("effective_scope", sa.String(256)),
        sa.Column("target_category", sa.String(64)),
        sa.Column("target_id", UUID(as_uuid=True)),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("risk", sa.String(32), nullable=False),
        sa.Column("authorization_decision", sa.String(32)),
        sa.CheckConstraint("duration_ms >= 0", name="audit_duration_nonnegative"),
    )
    op.create_table(
        "idempotency_records", _id(), _owner(),
        sa.Column("client_id", UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("operation", sa.String(128), nullable=False),
        sa.Column("idempotency_key", UUID(as_uuid=True), nullable=False),
        sa.Column("payload_digest", sa.String(64)),
        sa.Column("outcome", JSONB),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("tombstoned_at", sa.DateTime(timezone=True)),
        *_timestamps(), _version(),
        sa.UniqueConstraint("client_id", "operation", "idempotency_key", name="uq_idempotency_claim"),
        sa.CheckConstraint("status IN ('claimed','completed','tombstoned')", name="idempotency_status_allowed"),
        sa.CheckConstraint("status != 'tombstoned' OR payload_digest IS NULL", name="tombstone_no_digest"),
    )
    op.create_table(
        "jobs", _id(), _owner(),
        sa.Column("client_id", UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="SET NULL")),
        sa.Column("job_type", sa.String(128), nullable=False),
        sa.Column("payload_ref", sa.Text(), nullable=False),
        sa.Column("idempotency_key", UUID(as_uuid=True)),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_owner", sa.String(128)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("claim_token", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_summary", sa.String(512)),
        sa.Column("result_refs", JSONB),
        *_timestamps(), _version(),
        sa.CheckConstraint("state IN ('queued','leased','succeeded','retry_wait','dead_letter','cancelled')", name="job_state_allowed"),
        sa.CheckConstraint("attempts >= 0 AND max_attempts BETWEEN 1 AND 5 AND attempts <= max_attempts", name="job_attempt_bound"),
        sa.CheckConstraint("claim_token >= 0", name="job_claim_token_nonnegative"),
    )
    op.create_table(
        "derivation_edges", _id(), _owner(),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), nullable=False),
        sa.Column("derived_type", sa.String(64), nullable=False),
        sa.Column("derived_id", UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("contribution_weight", sa.Numeric(8, 4)),
        sa.Column("generator_version", sa.String(128), nullable=False),
        *_timestamps(), _version(),
        sa.CheckConstraint("role IN ('extracted_from','summarized_from','embedded_from','inferred_from','supported_by','contradicts')", name="derivation_role_allowed"),
    )
    op.create_table(
        "derived_contents", _id(), _owner(),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("derivation_version", sa.String(128), nullable=False),
        sa.Column("generator_kind", sa.String(64), nullable=False),
        sa.Column("generator_version", sa.String(128), nullable=False),
        sa.Column("derived_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.String(32)),
        sa.Column("confidence_inputs", JSONB),
        sa.Column("payload_ref", sa.Text()),
        sa.Column("state", sa.String(32), nullable=False),
        *_information(), *_timestamps(), _version(),
        sa.UniqueConstraint("owner_id", "target_type", "target_id", "kind", "derivation_version", name="uq_derived_version"),
        sa.CheckConstraint("canonicality = 'derived'", name="derived_canonicality_only"),
        sa.CheckConstraint("kind IN ('extracted_text','summary','embedding','description','transcript','digest','archive_listing')", name="derived_kind_allowed"),
        sa.CheckConstraint("state IN ('candidate','active','superseded','failed','orphaned','recomputing')", name="derived_state_allowed"),
    )
    op.create_table(
        "review_inbox_items", _id(), _owner(),
        sa.Column("item_type", sa.String(64), nullable=False),
        sa.Column("subject_refs", JSONB, nullable=False),
        sa.Column("proposal", JSONB, nullable=False),
        sa.Column("risk", sa.String(32), nullable=False),
        sa.Column("evidence", JSONB, nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("resolver_id", UUID(as_uuid=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("expected_version", sa.Integer()),
        *_timestamps(), _version(),
        sa.CheckConstraint("item_type IN ('ambiguity','conflict','merge_candidate','profile_confirmation','deletion_confirmation','permission_change','failed_reconciliation')", name="review_item_type_allowed"),
        sa.CheckConstraint("state IN ('open','approved','rejected','deferred','resolved')", name="review_item_state_allowed"),
        sa.CheckConstraint("expected_version IS NULL OR expected_version >= 1", name="review_expected_version_positive"),
    )
    op.create_index("ix_jobs_claimable", "jobs", ["state", "available_at", "priority"])
    op.create_index("ix_derivation_source", "derivation_edges", ["owner_id", "source_type", "source_id"])
    op.create_index("ix_derived_target", "derived_contents", ["owner_id", "target_type", "target_id"])


def downgrade() -> None:
    schema = op.get_bind().scalar(sa.text("SELECT current_schema()"))
    if not isinstance(schema, str) or not schema.startswith("brain_migration_test_"):
        raise RuntimeError("downgrade is limited to isolated synthetic test schemas; restore production from verified backup")
    for table in reversed(CREATED_TABLES):
        op.drop_table(table)
