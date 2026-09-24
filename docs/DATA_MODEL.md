# Personal Brain V1 - Data Model

Canonical source of entity definitions: `specs/001-personal-brain-v1/data-model.md`.
This page is the operator summary; the spec is authoritative.

## Authority and intake

- Owner, Client, Credential, OAuthGrant, PermissionGrant.
- IntakeRequest (unique `client_id + operation + idempotency_key`), RawInput
  (immutable canonical body), Idempotency (claim/tombstone), AuditEvent
  (body-free), Job (durable), DerivationEdge, DerivedContent, ReviewInboxItem.

## Life records

- Document, Expense (`numeric(20,4)`, currency required), Todo (4 states),
  Event (acyclic parent), Experience, Entity (8 types), Relation (same owner).

## Memory and self model

- Memory (8 lifecycle states), SelfClaim (A/B/C, establishment, review),
  Evidence, Conflict (>=2 participants).

## Projects

- Project, ModuleCard (fresh/stale/unknown), ProjectTask, Checkpoint, Decision,
  Constraint, ChangeEvent, Milestone, WorkspaceObservation.

## Assets and search

- Asset, AssetBlob (unique `sha256+size`), SearchIndexEntry (authorized scope,
  no secret sensitivity), ContextRequest, ContextPackage.

## Lifecycle and operations

- DeletionPlan, DeletionAction (opaque ledger), BackupSet, RestoreVerification,
  HealthFinding, Notification, ExternalSource, ImportCheckpoint.

## Migrations

Chain: 0001_authority_core -> 0002_life_records -> 0003_lineage_constraints ->
0004_memory_self_model -> 0005_project_brain -> 0006_assets_search ->
0007_retrieval_context -> 0008_lifecycle_deletion -> 0009_external_sources ->
0010_operations -> 0011_notifications. Entities are created once; later
migrations only reference them.
