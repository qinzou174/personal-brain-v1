# Backup and Restore (US10)

## Deployed path (personal-brain-v1-prod, 2026-09-25)

The running stack uses one script and one off-host copy; the US10 acceptance
scripts below remain as the specification-level reference.

```bash
# On the deployment host (reads secrets through the containers that own them):
deploy/scripts/prod-backup.sh          # -> /home/kms/personal-brain-v1-backups/personal-brain-prod-<stamp>.tar.age
# On the operator machine (off-host copy + sha256 verification):
uv run python deploy/windows-local/pull_backup.py   # -> E:\Personal-Brain-V1-local\backups\...
```

- Bundle contents: `database.pg_dump` (pg_dump -Fc from the live server),
  `data-root.tar.gz` (`/srv/brain/data`), `api-secrets.tar.gz` +
  `db-secrets.tar.gz` (mounted secret files), `artifacts.sha256`, `manifest.json`.
- Encryption: `openssl enc -aes-256-cbc -pbkdf2 -iter 200000`; the passphrase is
  kept in the operator home (`~/.brain-backup-passphrase`, mode 600) and must
  survive independently of the bundles.
- Retention: newest 7 bundles on the host, newest 5 on the operator machine.
- Client credentials are deliberately **not** backed up: re-issue them with
  `personal_brain_server rotate-client` after a restore.

Restore outline (validated: checksums verified, `pg_restore --list` on the dump
shows a complete 257-entry archive):

```bash
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in <bundle>.tar.age \
  -out bundle.tar -pass file:~/.brain-backup-passphrase
tar -xf bundle.tar && sha256sum -c artifacts.sha256
docker exec -i <db-container> pg_restore -U brain -d brain --clean --if-exists < database.pg_dump
# data root -> the brain-data volume; api/db secrets -> the mounted secret files
```

## Specification reference (US10 acceptance)

### Backup

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
