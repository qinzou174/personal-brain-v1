# Encrypted backup set — T183 evidence (2026-09-23)

## Task marker

T183 is checked complete in `specs/001-personal-brain-v1/tasks.md`. This
document records evidence produced by the current run only; no static or
placeholder reference is admitted.

## What was produced

A database-consistent, age-encrypted backup set from the isolated
`personal_brain_20260923_test` PostgreSQL 16.15 (46 public tables, 1 owner, 1
expense row) plus asset/config/ledger/authoritative manifests:

- Temporary container `brain-pg-20260923` on 192.168.10.7 (pgvector:pg16) was
  the backup source; `pg_dump --format=custom` with a server-matching client.
- Ephemeral `brain-backup-tools` container (age + pg16 command-line tools)
  produced the bundle: `database.pg_dump`, `assets.tar`, `configuration.tar`,
  `deletion-ledger.json`, `authoritative-sources.json`, `artifacts.sha256`,
  `manifest.json`, encrypted with `age --encrypt --recipients-file`.
- Final artifact:
  `/home/kms/personal-brain-v1-backups/daily/personal-brain-20260923T052848Z-daily.tar.age`
  (174,312 bytes) + sibling `.sha256`.
- Age identity is held separately from the recipients file; the recipients
  public key is the only thing handed to the backup script. Identity never
  enters the bundle.

## Executed verification

1. `age --decrypt --identity <identity> <bundle>` succeeded.
2. `sha256sum -c artifacts.sha256` — 6/6 artifacts OK (pg_dump, assets.tar,
   configuration.tar, deletion-ledger.json, authoritative-sources.json,
   manifest.json).
3. Isolated restore to fresh database `personal_brain_restore_test`:
   - restored `expenses` count = **1** (matches source),
   - restored `owners` count = **1** (matches source),
   - public tables = **46** (matches source inventory),
   - `pg_restore` completed without error.
4. Capacity-safe retention: tier daily keeps 7 newest; the producer removed
   older candidates only under an escaped-realtime guard scoped to the tier
   directory.
5. Fail-closed posture: missing destination/asset/config/manifest/recipient/
   hooks and improper permissions abort before any pg_dump (tested by the
   existing `tests/contract/test_backup_script.py`).

## Manifest

```json
{"format":1,"covered_at":"2026-09-23T05:28:48Z","tier":"daily","database_artifact":"database.pg_dump","asset_manifest":"artifacts.sha256","configuration_artifact":"configuration.tar","deletion_ledger":"deletion-ledger.json","authoritative_sources":"authoritative-sources.json","schema_inventory_sha256":"eed28347cdbea3a9fd19b3a179a0e4c9d3fe43c9af9af1eeafb8c35162eb2a3b","encryption":"age","state":"complete"}
```

## Honest boundaries

- The independent destination here is a new sibling directory
  `/home/kms/personal-brain-v1-backups` on the same host root filesystem. Per
  deployment-decision, that is suitable as a verified local restore rehearsal
  but **not** an off-host disaster medium. Off-host backup and real personal
  data remain gated; T187 will record the backup tailing as completion-gated.
- No real personal data was involved; the backup source is the isolated
  `*_test` database seeded by the current run.
- The temporary containers and the isolated restore database will be removed
  when the pass series concludes.