# Operations (V1)

- **Health**: per-component states (db/assets/relations/indexes/jobs/backups/
  restore/capacity); failures reported without masking; HTTP stays available.
- **Maintenance**: daily backup 02:00, weekly + post-migration restore
  verification, monthly full restore; single scheduler.
- **Retention**: logs 30d, temporary 24h, notifications 90d, indexes rebuildable.
- **Migration**: preflight + backup gate + post-validation; rollback via restore.
- **Notification triggers**: todo deadline, sync/index failure, backup/storage
  failure, Brain health failure; 60-min cooldown, 10-min merge, daily recap.
- See `docs/acceptance/operations-schedule.md` and
  `deploy/maintenance-schedule.yaml`.
