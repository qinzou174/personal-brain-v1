# Offline queue and durable worker evidence — 2026-09-23

Status: **PASS** for T181's implementation scope.

- The local pending-write queue persists AES-256-GCM ciphertext only; its key is externally supplied and never stored beside the queue. The directory/file is private-mode where POSIX permissions apply.
- Secret-like payloads are rejected before encryption or disk writes. Entry and byte ceilings are 1,000 and 100 MiB.
- Replays are insertion ordered and idempotency-key preserving. Client revocation, version conflict and uncertain delivery stop replay without claiming a save.
- Durable jobs are claimed in short transactions, executed outside the claim transaction, heartbeated every 20 seconds, progress-updated under the fencing token and rechecked before execution and commit.
- The production registry covers canonical/search indexing, project bootstrap/refresh, asset parse/reprocess, deletion reconciliation, health/retention maintenance and owner-inbox notification work.
- Client activity, value-free secret admission and source version/updated-time are checked at both execution fences. Unknown/nonretryable jobs dead-letter; retryable failures retain the bounded 5/30/120/600-second schedule and five-attempt ceiling.
- Physical PostgreSQL evidence in `postgres-search-2026-09-23.md` proves an actual queued indexing job was claimed, progressed, committed and became searchable.

Automated result after these changes: **393 passed, 13 skipped, 0 failed** without the optional DSN; the authoritative DSN run before the final registry-coverage assertion was **392 passed, 11 skipped, 0 failed**.
