# MCP full-surface evidence — 2026-09-23

Status: **PASS** for T174's implemented protocol-adapter scope.

## Evidence

- The remote Streamable HTTP adapter implements discovery, protocol-version enforcement, initialize, session IDs, `tools/list`, `tools/call`, stable structured results, bearer re-authentication on every request and exact Origin checks.
- The production server advertises all **27/27** FR-099 tool names; none are filtered out as unimplemented.
- Every tool has a closed JSON input schema and never accepts caller-selected credentials, client IDs or grants in tool arguments.
- Operation-status lookup, structured finance/todo reads, project recovery/freshness, workspace sync, self context, PostgreSQL hybrid search and bounded base64 asset upload are bound to the credential-derived service.
- The local stdio bridge now proxies the real remote MCP lifecycle and carries the remote session ID. Credentials come from a file, are sent only as the bearer header and never appear in protocol output.
- Public cleartext HTTP endpoints are rejected; only HTTPS or explicitly private/loopback HTTP endpoints are accepted by the bridge.

## Automated verification

- Contract tests exercise remote session/auth/origin behavior, all 27 schemas and stdio-to-HTTP forwarding across initialize, list and call.
- The physical PostgreSQL test exercises the revised 0001..0011 chain, Chinese FTS, version-matched pgvector retrieval, provenance/warnings and reverse migration.

## Boundary

The adapters are implemented and locally verified. Actual TRAE, Cursor and ChatGPT account interoperability remains T186 `EXTERNAL_VERIFICATION_PENDING` and is not claimed here.
