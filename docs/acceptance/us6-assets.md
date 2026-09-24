# US6 Scenario D evidence: assets, archive and reprocessing

Date: 2026-09-23 Asia/Shanghai. Synthetic data only.

## Evidence

| Requirement | Observed outcome | Evidence source |
|---|---|---|
| FR-031..FR-033 identity/dedupe | Duplicate bytes share one blob while each source keeps a distinct asset; identity is `(sha256, size)` | `tests/acceptance/test_assets.py::test_duplicate_bytes_share_blob_but_keep_distinct_sources`, `tests/unit/test_asset_tools.py` |
| FR-039 integrity | Integrity scan distinguishes valid vs hash_mismatch; missing bytes -> missing | `test_integrity_detects_hash_mismatch`, `packages/domain/.../integrity.py` |
| FR-038/ER-05 archive safety | Archive listings reject traversal/absolute/UNC entries and enforce entry/name limits | `test_archive_traversal_and_limits_rejected`, `archive_processor.py` |
| FR-032/033/040 storage | Local backend verifies hash/size before atomic promotion; caller never picks the path | `packages/infrastructure/.../storage/local.py`, `base.py` |
| FR-034/037 processors | Document text extraction is bounded and preserves the original; audio metadata/transcription is optional/derived | `document_processors.py`, `audio_processor.py` |
| Migration 0006 | Only Asset/AssetBlob/SearchIndexEntry created with unique blob identity and search sensitivity checks | `tests/migration/test_0006_assets_search.py` |

Suite result: 6 relevant tests passed. Storage backend atomic promotion is
defined but exercised only in unit scope (no full fixture upload/restore cycle —
that is the US10 backup/restore gate).

## Remaining risks

- SC-009 (seven asset classes full-fixture upload -> backup -> restore with
  matching SHA256+size) is not yet run; it requires the US10 backup/restore
  pipeline and the target host.
- Real PDF/DOCX/image/audio processing beyond plain text/markdown stays pending
  until format-specific extractors are bound; unsupported formats route to
  pending_review as required.
