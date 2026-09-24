# US10 Scenario K/L evidence: operations, backup and restore

Date: 2026-09-23 Asia/Shanghai. Synthetic data only; no real backup ran on the
target host, and no real personal data was exported.

## Evidence

| Requirement | Observed outcome | Evidence source |
|---|---|---|
| FR-083/084 job crash/dead-letter | A job exhausting its 5 attempts transitions to dead_letter; lease/fencing unchanged | `tests/acceptance/test_operational_health.py::test_exhausted_failing_job_goes_dead_letter` |
| FR-092 aggregate health | Per-component health is reported without collapsing failures into service availability | `test_health_aggregates_without_collapsing_failures`, `tests/unit/test_health_api.py` |
| FR-094/096 backup inventory | Backup inventory lists DB artifact, asset manifest (sha256) and retention tiers | `tests/restore/test_full_restore.py::test_backup_inventory_lists_tiers_and_hashes` |
| FR-096 tier retention | 7/28/90-day daily/weekly/monthly boundaries; deleted-data disclosure distinguishes production purge vs backup purge due | `tests/restore/test_backup_retention.py`, `tests/integration/test_doctor_findings.py` |
| FR-095/097 isolated restore | Restore verification computes fixture percent and asset-hash fidelity; verified only at 100% | `test_restore_verification_records_results_not_passed_by_default` |
| FR-092 doctor | Low-disk/critical and corrupt-asset findings are surfaced | `tests/integration/test_doctor_findings.py::test_doctor_detects_low_disk_and_corrupt_asset` |
| FR-093 growth | Logs/temp/notifications/index retention ceilings are bounded | `operations/growth.py` |
| Migration 0010 | BackupSet/RestoreVerification/HealthFinding created once | `tests/migration/test_0010_operations.py` |
| FR-094/040/076 export | Portable export manifest excludes credentials and maps sources/blobs | `tests/restore/test_portable_export.py` |

Suite result: 12 relevant tests passed across acceptance/restore/integration/unit.

## Remaining risks

- Real backup/restore on the target host, independent backup medium, encrypted
  retention and ER-10 full-rotation sampling remain **pending** — real-data
  deployment is hard-gated on this evidence (deployment-decision.md).
- RPO 24h / RTO 4h are proposals; no measurement was performed.
- deploy/scripts backup.sh/verify-restore.sh/migrate.sh are written but not
  executed; they run only on the approved target host after Phase 0.
