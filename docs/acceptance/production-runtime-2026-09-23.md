# Production-shaped LAN runtime acceptance (2026-09-23)

## Scope

Evidence for T188-T192 on the approved LAN host `kms@192.168.10.7`. No Nginx
site, soft-router service, port 53/7890, public route or real personal record was
changed. All business records below are synthetic acceptance data.

## Deployment boundary

- Project: `/home/kms/personal-brain-v1`; runtime data:
  `/home/kms/personal-brain-v1-data`.
- Compose API listens inside its container and publishes only
  `192.168.10.7:18081` on the host.
- PostgreSQL and worker publish no host port. The migration service exited 0 at
  Alembic `0011_notifications (head)` before API/worker startup.
- Database password, database DSN and token pepper are file-backed Compose
  secrets. No reusable credential is embedded in Compose, the image or Git.
- The target's ignored `deploy/.env` is mode 0600 and stores only those secret
  file paths, allowing repeatable Compose status/start operations without
  copying secret values into shell history.
- `/ready`, called on the server and from the Windows LAN client, returned
  `ready=true` and `database=worker=storage=ok`.

## Owner and client lifecycle

- The operator CLI created the first owner and provisioned a dedicated TRAE CN
  client. Its bearer was written once to an ACL-restricted file and was never
  printed.
- Rotation, revocation, listing and owner-aware body-free audit paths are
  covered by integration tests.
- The Windows credential file is
  `%USERPROFILE%\.personal-brain\trae-cn-credential`; the TRAE MCP configuration
  contains only this path, not the bearer value.

## Actual bridge and business behavior

The real `personal_brain_bridge` stdio process connected to the deployed `/mcp`
endpoint and completed:

1. MCP initialize and tool discovery.
2. Canonical note, CNY 38 expense and todo writes.
3. Exact expense summary returning `38.0000 CNY`.
4. Worker indexing followed by retrieval of the note.
5. Project request denied before exact project grant.
6. Owner grant `write`, task creation and fresh-context recovery.
7. Grant removal, verified `SCOPE_DENIED`, then restoration of `write` for
   continued synthetic use.
8. API/worker restart followed by successful reads of the expense and project
   task, proving persistence across process restart.

TRAE CN's real user `mcp.json` now contains the `personal-brain` stdio entry and
parses successfully. Because the IDE was already running and the computer-use
surface could not attach to native apps, visible in-IDE discovery/call remains
PENDING until the TRAE window is reloaded. This is not claimed as a completed
T186 row.

## Regression

- Final local suite without a PostgreSQL DSN: **412 passed, 23 skipped, 0
  failed**. The additional skips are the explicitly gated PostgreSQL journeys
  and physical migration tests.
- Full isolated PostgreSQL/pgvector suite after T188-T191:
  **423 passed, 12 skipped, 0 failed**.
- The 12 skips are the deliberately gated real-client/file-environment cases:
  eight cross-client file fixtures, three TRAE/Cursor/ChatGPT real-client cases
  and one POSIX permission case on Windows.
- The temporary regression database, container and SSH tunnel were removed
  after the run. The production-shaped LAN stack remains running intentionally.

## Verdict

T188-T192 PASS. There are zero unresolved CRITICAL findings in the executed LAN
surface. T186 remains EXTERNAL_VERIFICATION_PENDING for visible TRAE IDE use,
Cursor, ChatGPT/HTTPS-OAuth and real Trilium. Independent off-host backup and a
restore rehearsal are still required before importing real personal data.
