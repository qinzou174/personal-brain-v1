# Operational Contracts

## Phase 0 Environment Report Contract

The read-only report must record observation time, target host identity, commands or evidence
used, observed values, unknowns, and risks for OS/architecture, CPU/RAM/disk, container runtime,
running services, networks, listening ports, reverse proxy, tunnel/private network, database,
Git, human knowledge tool, backup destination, DNS/TLS, and existing path ownership.

It must not install, restart, reconfigure, upload, delete, bind a port, change firewall/auth,
or collect secret values. Each proposed deployment choice remains `proposed` until supported by
observed evidence.

## Background Job Contract

- Acceptance and job creation commit with the canonical transaction.
- Workers claim jobs atomically with a lease and unique worker identity.
- A lease can expire and be reclaimed; handlers are idempotent.
- Retry count, next-attempt time, safe error code, and safe error summary are durable.
- Exhausted retries move to `dead_letter`; they are never reported as completed.
- Cancellation cannot interrupt a canonical commit already completed; compensating behavior is
  explicit and audited.

## Workspace Bridge Contract

- The bridge is configured with one exact normalized workspace root per session/client scope.
- Every requested path is resolved and containment-checked before access; links/reparse points
  cannot escape the root.
- Default collection is revision, branch/ref, status, changed paths, bounded diff summary,
  relevant file hashes, and approved source structure.
- Secrets, excluded paths, unrelated repositories, browser state, and broad user-directory
  enumeration are rejected.
- Uncommitted content is described as observed local state, not durable cross-device backup.

## Asset Intake Contract

- Streamed bytes are size-limited, hashed during intake, written to a temporary isolated path,
  verified, then atomically promoted to content-addressed storage.
- Metadata cannot choose an arbitrary filesystem path.
- A duplicate blob creates a new source/Asset relationship but not duplicate bytes.
- Archive listing has limits for bytes, entries, nesting, names, and time. Extraction is a
  separate explicit job with traversal and secret filtering.
- Any parser output is derived and cannot mutate the original blob.

## Secret Filter Contract

- Filtering occurs before ordinary persistence and indexing when plaintext is available.
- Match rules cover explicit excluded filenames/types plus bounded content detectors.
- A match records only detector/rule ID, source category, time, and `secret_skipped`; never the
  matched value or surrounding sensitive text.
- False-positive review must use an isolated owner-authorized path and cannot expose a value in
  logs or normal audit.

## Migration Contract

Each migration declares source version, target version, forward action, rollback or restore
strategy, affected canonical/derived entities, estimated lock/storage impact, preflight query,
post-validation query, and backup prerequisite. A production migration is incomplete until
post-validation and health checks pass.

## Backup Contract

- Backup inventory covers canonical database, asset blobs/manifests, required non-secret
  configuration, migration state, and selected external authority references.
- Each artifact has size, hash, creation time, encryption/retention metadata, and status.
- A database backup uses a database-consistent export; copying live data files alone is not a
  valid complete backup.
- Retention policy is capacity-aware and records deletions.

## Restore Verification Contract

Restore runs against an isolated target and records:

1. Schema/migration version and canonical entity counts.
2. Sampled exact expense/todo queries.
3. Sampled lineage, relation, self-claim, and project-context traversals.
4. Permission allow/deny and revoked-client cases.
5. Sampled asset byte hashes and missing-reference checks.
6. Background job and index rebuild readiness.
7. Result, failures, evidence references, and independent verification time.

Backup status and restore-verification status are separate health dimensions.

## Health Contract

Health reports component state (`healthy | degraded | failed | unknown`), evidence time,
severity, and actionable summary for API, canonical store, worker/jobs, index freshness, asset
integrity, module staleness, inbox backlog, last backup, last verified restore, storage capacity,
and notification delivery. A shallow HTTP response cannot make the aggregate system healthy.

## Notification Contract

Only explicit V1 triggers—todo deadline, project sync/index failure, backup/storage failure, and
Brain health failure—are enabled by default. Detection produces a candidate. Central policy
decides suppression or delivery using severity, priority, cooldown, merge key, duplicate key,
owner preferences, and channel availability. Non-urgent trend detection does not imply notify.

## Acceptance Evidence Contract

Every delivery phase records requirement/scenario IDs, environment identity, precondition,
action, authoritative observed outcome, produced evidence, failures, unresolved risks, and
reviewer decision. A command exit code, running container, HTTP 200, row write, or generated
file is supporting evidence only; it is not sufficient alone for user-visible acceptance.


## 规范参数与补充契约

本契约必须合读[ER](../execution-rules.md)和[协议/部署契约](protocol-deployment.md)。ER的状态、限值、失败路径优先于本文件简述：quarantine不等于canonical；解析失效不称ready；无当前工作区观察为unknown；删除预览无副作用；备份需一致cutoff、恢复前重放删除ledger并满足ER-10证据。所有运行证据待实施授权。
