# Operations schedule (US10)

Date: 2026-09-23. Proposal only; the maintenance schedule YAML
(`deploy/maintenance-schedule.yaml`) is the machine-readable contract.

## Cadence

- Daily backup at 02:00 Asia/Shanghai by a single scheduler.
- Restore verification weekly (Sunday 04:00) and mandatory after any migration.
- Full fixture restore monthly (first Saturday): ER-10 100% fixture + deterministic
  production samples (counts, permissions, representative queries, asset hashes).
- Storage alerts at 15% disk warn / 5% critical.

## Gates

- No production write before an independently verified restore point.
- RPO 24h / RTO 4h remain **proposed** until measured on the target host.
- No service is served from an unverified restore; health reports component state
  without masking failures.
