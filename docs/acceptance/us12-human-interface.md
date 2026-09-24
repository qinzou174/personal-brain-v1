# US12 Scenario N evidence: human knowledge interface

Date: 2026-09-23 Asia/Shanghai. Synthetic data only.

## Evidence

| Requirement | Observed outcome | Evidence source |
|---|---|---|
| FR-100/101 source-preserving import | Imported notes keep source identity and `original_document` classification; import is paged/idempotent with a checkpoint | `tests/acceptance/test_human_knowledge_interface.py`, `tests/integration/test_trilium_import.py` |
| FR-100 removable interface | Disabling the human-knowledge interface leaves core Brain available; external reported `disabled` | `test_core_works_with_interface_disabled`, `test_trilium_disabled_leaves_core_healthy` |
| FR-102 optional digests | Daily/weekly/monthly digest navigation is source-linked and versioned; automatic generation is optional, never gating V1 | `packages/domain/.../retrieval/digests.py` |
| Migration 0009 | ExternalSource/ImportCheckpoint with bounded source identity/health/status | `tests/migration/test_0009_external_sources.py` |

Suite result: 5 relevant tests passed. Trilium deployment/connection remains
EXTERNAL_VERIFICATION_PENDING per [TRILIUM_SETUP](../TRILIUM_SETUP.md) — the
integration contract is wired but no real endpoint/credential was touched.

## Remaining risks

- The real Trilium connection, paged API read and secret-file provisioning require
  owner-provided endpoint details and belong to the Release deployment phase.
- Automatic digest generation remains optional by design and is not implemented.
