# Operations (V1)

- **Health**: per-component states (db/assets/relations/indexes/jobs/backups/
  restore/capacity); failures reported without masking; HTTP stays available.
  The daily `health_check` job raises one inbox notification when dead-letter
  jobs exist (60-min cooldown), so the owner learns about failures proactively.
- **Living backend (daily schedule, local time)**: `daily_digest` 03:10,
  `promote_candidates` 04:10, `retention_sweep` 04:20, `conflict_scan` 04:30,
  `retention_maintenance` 04:40, `health_check` 08:00 — enqueued by the worker's
  scheduler once per owner and day (`personal_brain_worker/scheduler.py`).
- **Background model budget**: extraction and digest jobs share a per-day job
  quota (`BRAIN_LLM_DAILY_QUOTA`, default 200); exceeding it degrades to
  rules-only behavior and never blocks canonical writes.  Per-call limits
  (timeout, sensitivity, secret rejection) still apply through the model gateway.
- **Maintenance**: daily backup 02:00, weekly + post-migration restore
  verification, monthly full restore; single scheduler.
- **Retention**: logs 30d, temporary 24h, notifications 90d, indexes rebuildable.
- **Migration**: preflight + backup gate + post-validation; rollback via restore.
- **Notification triggers**: todo deadline, sync/index failure, backup/storage
  failure, Brain health failure; 60-min cooldown, 10-min merge, daily recap.
- See `docs/acceptance/operations-schedule.md` and
  `deploy/maintenance-schedule.yaml`.
