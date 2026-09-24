# US11 Scenario M evidence: conservative proactivity

Date: 2026-09-23 Asia/Shanghai. Synthetic data only.

## Evidence

| Requirement | Observed outcome | Evidence source |
|---|---|---|
| FR-089 explicit triggers | Todo deadline and backup/storage failures notify with high priority; preference trend is detected but does not notify by default | `tests/acceptance/test_notifications.py::test_todo_deadline_triggers_and_priority`, `test_trend_does_not_notify_by_default` |
| FR-091/ER-11 cooldown/merge | Repeated equivalent failure is merged/suppressed within the 60-minute cooldown and the 10-minute merge window; first occurrence sends | `test_repeated_failure_merged_within_cooldown`, `notification_policy.py` |
| FR-084 safe dispatch | Dispatch job delivers to the mandatory owner Inbox; external channels are optional | `apps/worker/.../notification_jobs.py` |
| Migration 0011 | Notifications table with trigger/channel/state enums and dedupe index | `tests/migration/test_0011_notifications.py` |

Suite result: 4 relevant tests passed across acceptance/migration.

## Remaining risks

- Channel delivery (email/push) is contract-defined but not implemented; the
  owner Inbox remains the mandatory acknowledgement surface (ER-06/ER-11).
- Date-only 09:00 scheduling rule is stated in the policy module; end-to-end
  scheduler wiring belongs to the Release deployment phase.
