# Bridge Setup

The bridge is a Windows-first local MCP process that observes only an approved
workspace root.

- `apps/bridge/personal_brain_bridge`: stdio transport, workspace containment,
  Git observation, bootstrap scan, incremental sync, offline pending store.
- Approved root proof is required for every sync; paths outside the root are
  rejected before any read.
- stdout is protocol-only; logs go to stderr.
- No secret values cross the bridge; secret-like files are excluded from the
  bootstrap scan.

## Activation

The bridge requires these environment values:

- `BRAIN_BRIDGE_CLIENT_ID`: the configured local client identity label.
- `BRAIN_REMOTE_MCP_URL`: the exact `/mcp` endpoint. Plain HTTP is accepted only
  for a loopback or private-LAN address; public endpoints must use HTTPS.
- `BRAIN_CREDENTIAL_FILE`: a private file containing the opaque bearer
  credential. The credential is never accepted inline in MCP configuration and
  is never written to stdout.

Launch with `python -m personal_brain_bridge`. The bridge forwards initialize,
session, discovery and tool calls to the authoritative server. It does not keep
an independent memory store. The configured TRAE CN bridge path has been tested
against the live LAN deployment; visible IDE discovery and the other real
clients remain tracked in the external client matrix.
