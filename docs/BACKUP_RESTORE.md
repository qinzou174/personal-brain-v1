# Backup and Restore (US10)

## Backup

- Daily at 02:00 Asia/Shanghai by a single scheduler.
- Backup includes canonical DB, asset manifest (sha256), Trilium/Git/config and
  the deletion ledger. Cutoff is frozen at backup start.
- Tiers: 7 daily / 4 weekly / 3 monthly subject to the ER-10 floor.

## Restore verification

- Weekly and after every migration; monthly full-fixture restore.
- Fixture 100% fidelity; production samples (counts, permissions, representative
  queries, asset hashes) per ER-10 with recorded seed.
- Verified only when every check passes; RPO 24h / RTO 4h remain proposed until
  measured on the target host.

## Deleted data

- `production_purged` is reported separately from `backup_purge_due`; never claim
  "all copies gone" before the backup purge window.
- The deletion ledger is replayed before serving after any restore; indexes are
  rebuilt afterwards.

## Commands

`deploy/scripts/backup.sh`, `deploy/scripts/verify-restore.sh`,
`deploy/scripts/migrate.sh` (Linux target host only, after Phase 0 approval).

`backup.sh` intentionally refuses defaults for authoritative paths. Supply an
independent `BRAIN_BACKUP_DEST`, asset/config roots, deletion-ledger and
authoritative-source manifests, an `age` recipients file, executable write
freeze/thaw hooks, and libpq `PGSERVICEFILE`/`PGPASSFILE` plus a non-secret
`BRAIN_PG_SERVICE_NAME`. Select `BRAIN_BACKUP_TIER` as `daily`, `weekly` or
`monthly`. Keys are not accepted from environment variables or written into the
archive.

The script checks capacity before freezing, creates the database export and
asset/config/ledger manifests under one coordinated cutoff, thaws writes,
hashes every artifact, encrypts the complete bundle, atomically publishes it,
and prunes only resolved files inside the chosen tier directory. Any missing
input, command, capacity, hash/encryption step or coordination hook aborts the
run. Script readiness is not backup success: T183 remains open until an
independent destination/key is selected and the resulting set passes isolated
restore verification.
